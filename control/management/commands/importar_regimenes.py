import hashlib
from collections import Counter
from pathlib import Path
from openpyxl import load_workbook
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from control.models import CuentaVacacion,Trabajador,normalizar
from control.regimenes import normalizar_regimen
from control.audit import registrar,snapshot


def leer_regimenes(path):
    wb=load_workbook(path,read_only=True,data_only=True)
    try:
        sheet=wb['Resumen'];header=None;mapping={};unidentified=[]
        for row in sheet.iter_rows(values_only=True):
            if header is None:
                labels=[normalizar(str(v or '')).replace('.','') for v in row]
                if 'dni' in labels and 'reg labor' in labels:
                    header=(labels.index('dni'),labels.index('reg labor'))
                continue
            dni,raw=row[header[0]],row[header[1]]
            if not dni:continue
            dni=str(dni).strip()
            if not dni.isdigit() or len(dni)!=8:raise ValueError('DNI inválido en la clasificación; no se importó nada.')
            regime=normalizar_regimen(raw)
            if dni in mapping and mapping[dni]!=regime:raise ValueError('DNI con regímenes contradictorios; no se importó nada.')
            mapping[dni]=regime
            if not regime:unidentified.append(dni)
        if header is None or not mapping:raise ValueError('No se encontraron las columnas DNI y reg. Labor en Resumen.')
        return mapping,unidentified
    finally:wb.close()


class Command(BaseCommand):
    help='Previsualiza o asigna exclusivamente régimen laboral por DNI desde Resumen, sin modificar saldos.'
    def add_arguments(self,parser):
        parser.add_argument('archivo');parser.add_argument('--confirmar',action='store_true');parser.add_argument('--usuario')
    @transaction.atomic
    def handle(self,*args,**opts):
        try:mapping,unknown=leer_regimenes(opts['archivo'])
        except (ValueError,KeyError) as exc:raise CommandError(str(exc)) from exc
        user=None
        if opts['confirmar']:
            user=get_user_model().objects.filter(username=opts['usuario'],is_active=True).first()
            if not user or not user.has_perms(['control.change_trabajador','control.change_cuentavacacion']):
                raise CommandError('Indique usuario activo autorizado para editar trabajadores y control vacacional.')
        counts=Counter();checksum=hashlib.sha256(Path(opts['archivo']).read_bytes()).hexdigest()
        for model in (CuentaVacacion,Trabajador):
            qs=model.objects.filter(dni__in=mapping)
            if opts['confirmar']:qs=qs.select_for_update()
            rows=list(qs);duplicates=Counter(r.dni for r in rows)
            for obj in rows:
                if duplicates[obj.dni]>1:
                    counts['identidades_ambiguas']+=1;continue
                regime=mapping[obj.dni]
                if not regime:
                    counts['sin_regimen_informado']+=1;continue
                if obj.regimen_laboral==regime:
                    counts['sin_cambios']+=1;continue
                counts[model._meta.model_name]+=1
                if opts['confirmar']:
                    before=snapshot(obj)
                    model.objects.filter(pk=obj.pk).update(regimen_laboral=regime,updated_at=timezone.now())
                    obj.refresh_from_db();registrar(obj,user,'importar_regimen',before,{'fuente':'tipos de trabajadores.xlsx','sha256':checksum})
        counts['dni_fuente']=len(mapping);counts['dni_sin_clasificacion']=len(unknown)
        self.stdout.write(('Confirmado' if opts['confirmar'] else 'Previsualización')+': '+str(dict(counts)))
