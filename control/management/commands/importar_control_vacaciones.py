"""Importación privada y repetible; previa por defecto, confirmación transaccional."""
import hashlib
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from openpyxl import load_workbook
from control.models import CuentaVacacion, MovimientoVacacion
from control.audit import registrar


def fecha(v):
    return v.date() if isinstance(v,datetime) else v if isinstance(v,date) else None


def raw(sheet,row):
    return {str(c.column):c.value.isoformat() if isinstance(c.value,(datetime,date,time)) else c.value
            for c in sheet[row] if c.value is not None}


class Command(BaseCommand):
    help='Previsualiza el control vacacional; --confirmar aplica una vez el archivo revisado.'
    def add_arguments(self,p):
        p.add_argument('archivo')
        p.add_argument('--confirmar',action='store_true')
        p.add_argument('--usuario',default='admin_local')

    def handle(self,*args,**opts):
        from pathlib import Path
        path=Path(opts['archivo'])
        checksum=hashlib.sha256(path.read_bytes()).hexdigest()
        wb=load_workbook(path,data_only=True)
        if not {'Resumen','detalle'}.issubset(wb.sheetnames):
            raise CommandError('Se requieren las hojas Resumen y detalle.')
        s,d=wb['Resumen'],wb['detalle']
        summary=[r for r in range(4,s.max_row+1) if s.cell(r,1).value and s.cell(r,2).value]
        detail=[r for r in range(3,d.max_row+1) if d.cell(r,1).value]
        ids=[str(s.cell(r,1).value) for r in summary]
        if len(ids)!=len(set(ids)): raise CommandError('Hay DNI duplicados en RESUMEN; no se importa.')
        self.stdout.write(f'Previa: {len(summary)} fichas, {len(detail)} movimientos. Sin fusiones por nombre.')
        self.stdout.write('Carga independiente: no se buscan ni vinculan trabajadores o justificaciones. Códigos desconocidos, excepciones y déficits quedan para revisión.')
        if not opts['confirmar']: return
        user=get_user_model().objects.get(username=opts['usuario'])
        if not user.is_superuser: raise CommandError('La carga inicial exige administrador.')
        with transaction.atomic():
            # Evitar una segunda carga distinta sobre el histórico ya instalado.
            existing=CuentaVacacion.objects.filter(origen__checksum=checksum).exists()
            if existing:
                self.stdout.write('El archivo ya fue importado. No se duplicó ningún registro.')
                return
            if CuentaVacacion.objects.exists(): raise CommandError('Ya hay fichas. Revise el archivo antes de otra carga inicial.')
            accounts={}
            for r in summary:
                dni=str(s.cell(r,1).value)
                account=CuentaVacacion.objects.create(dni=dni,nombre=str(s.cell(r,2).value),
                    tipo=str(s.cell(r,3).value or ''),estado=str(s.cell(r,4).value or ''),
                    asignaciones={str(2022+i):str(s.cell(r,5+i).value) if s.cell(r,5+i).value is not None else None for i in range(9)},
                    origen={'checksum':checksum,'hoja':'Resumen','fila':r,'valores':raw(s,r)})
                accounts[dni]=account
                registrar(account,user,'importar',contexto={'hoja':'Resumen','fila':r})
            for r in detail:
                dni=str(d.cell(r,1).value)
                if dni not in accounts:
                    # Se conserva el movimiento huérfano sin inventar derechos ni nombre.
                    accounts[dni]=CuentaVacacion.objects.create(dni=dni,
                        nombre='Identidad pendiente de revisión',habilitada=False,
                        origen={'checksum':checksum,'sin_resumen':True},
                        notas='DNI presente en DETALLE y ausente en RESUMEN. Revisar identidad y asignaciones.')
                    registrar(accounts[dni],user,'importar_incidencia')
                days=d.cell(r,7).value
                code=str(d.cell(r,3).value or '')
                start,end=fecha(d.cell(r,5).value),fecha(d.cell(r,6).value)
                expected=(Decimal('0.5') if code=='32' else Decimal(0) if code=='09'
                          else Decimal((end-start).days+1) if code=='05' and start and end else None)
                try:
                    days=Decimal(str(days)) if days is not None else None
                except InvalidOperation:
                    days=None
                try:
                    permission=Decimal(str(d.cell(r,8).value or 0))
                except InvalidOperation:
                    permission=Decimal(0)
                pending=expected is None or days is None or days!=expected or not isinstance(d.cell(r,8).value,(int,float,type(None)))
                m=MovimientoVacacion.objects.create(cuenta=accounts[dni],periodo=str(d.cell(r,2).value or ''),
                    codigo=code,fecha=fecha(d.cell(r,4).value),inicio=start,fin=end,dias=days,
                    permiso_ley=permission,observaciones=str(d.cell(r,9).value or ''),
                    pendiente_revision=pending,origen_clave=f'{checksum}:{r}',
                    origen={'checksum':checksum,'hoja':'detalle','fila':r,'valores':raw(d,r)})
                registrar(m,user,'importar',contexto={'hoja':'detalle','fila':r})
        self.stdout.write(f'Carga completada: {len(accounts)} fichas incluidas las incidencias, {len(detail)} movimientos. Sin cambios en justificaciones.')
