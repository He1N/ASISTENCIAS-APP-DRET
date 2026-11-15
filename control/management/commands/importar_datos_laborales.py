"""Importar solo clasificación laboral del Resumen, nunca saldos ni movimientos."""
from collections import Counter
from datetime import date,datetime
from hashlib import sha256
from pathlib import Path
from openpyxl import load_workbook
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from control.models import CuentaVacacion,normalizar
from control.regimenes import normalizar_regimen
from control.audit import snapshot,registrar


def leer_datos(path):
    book=load_workbook(path,read_only=True,data_only=True)
    mapping={};columns=None
    try:
        for row in book['Resumen'].iter_rows(values_only=True):
            if columns is None:
                labels=[normalizar(str(v or '')).replace('.','') for v in row]
                aliases={'regimen laboral':'reg labor','fin de contrato':'fin contrato'}
                labels=[aliases.get(label,label) for label in labels]
                if all(x in labels for x in ('dni','reg labor','condicion','fin contrato')):
                    columns=[labels.index(x) for x in ('dni','reg labor','condicion','fin contrato')]
                continue
            dni,regime,condition,end=[row[i] if i<len(row) else None for i in columns]
            if not dni: continue
            dni=str(dni).strip()
            if not dni.isdigit() or len(dni)!=8: raise ValueError('DNI inválido; no se importó nada.')
            end=end.strftime('%d/%m/%Y') if isinstance(end,(date,datetime)) else str(end or '').strip()
            values=dict(regimen_laboral=normalizar_regimen(regime),condicion_laboral=str(condition or '').strip(),fin_contrato=end)
            if any(len(v)>100 for v in values.values()): raise ValueError('Dato laboral demasiado largo.')
            if dni in mapping and mapping[dni]!=values: raise ValueError('DNI con datos contradictorios.')
            mapping[dni]=values
        if not columns or not mapping: raise ValueError('No se encontró la clasificación laboral de Resumen.')
        return mapping
    finally: book.close()


class Command(BaseCommand):
    help='Previsualiza/importa régimen, condición y fin de contrato por DNI sin cambiar vacaciones.'
    def add_arguments(self,parser):
        parser.add_argument('archivo');parser.add_argument('--confirmar',action='store_true');parser.add_argument('--usuario')
    @transaction.atomic
    def handle(self,*args,**opts):
        try: mapping=leer_datos(opts['archivo'])
        except (ValueError,KeyError) as exc: raise CommandError(str(exc)) from exc
        user=None
        if opts['confirmar']:
            user=get_user_model().objects.filter(username=opts['usuario'],is_active=True).first()
            if not user or not user.has_perm('control.change_cuentavacacion'): raise CommandError('Usuario sin permiso para modificar cuentas.')
        counts=Counter();checksum=sha256(Path(opts['archivo']).read_bytes()).hexdigest()
        qs=CuentaVacacion.objects.filter(dni__in=mapping)
        if opts['confirmar']: qs=qs.select_for_update()
        for obj in qs:
            values=mapping[obj.dni].copy()
            # No borrar un régimen conocido por una clasificación sin informar.
            if not values['regimen_laboral']: values.pop('regimen_laboral')
            if all(getattr(obj,k)==v for k,v in values.items()): counts['sin_cambios']+=1;continue
            counts['cuentas']+=1
            if opts['confirmar']:
                before=snapshot(obj)
                for key,value in values.items(): setattr(obj,key,value)
                obj.save(update_fields=[*values,'updated_at'])
                registrar(obj,user,'importar_datos_laborales',before,{'sha256':checksum})
        counts['dni_fuente']=len(mapping)
        self.stdout.write(('Confirmado' if opts['confirmar'] else 'Previsualización')+': '+str(dict(counts)))
