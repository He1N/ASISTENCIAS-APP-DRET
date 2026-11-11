"""Clasificación informativa; el régimen no concede ni modifica días."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import CuentaVacacion, Trabajador, normalizar

REGIMENES=['DEC. LEG. 276','CAS','LEY 29944','LEY 30512','PRACTICANTE']

def normalizar_regimen(value):
    text=' '.join(str(value or '').upper().split())
    if text in {'NO EXISTE','SIN REGIMEN','SIN RÉGIMEN','SIN INFORMAR'}: return ''
    key=normalizar(text).replace('.','').replace(' ','')
    aliases={'decleg276':'DEC. LEG. 276','dl276':'DEC. LEG. 276','ley29944':'LEY 29944','ley30512':'LEY 30512','cas':'CAS'}
    return aliases.get(key,text)

def opciones_regimen():
    values=set(REGIMENES)
    values.update(Trabajador.objects.exclude(regimen_laboral='').values_list('regimen_laboral',flat=True))
    values.update(CuentaVacacion.objects.exclude(regimen_laboral='').values_list('regimen_laboral',flat=True))
    return [('', 'Todos los regímenes'),('__sin__','Sin régimen informado')]+[(x,x) for x in sorted(values)]

def filtrar_regimen(qs,value,field='regimen_laboral'):
    return qs.filter(**{field:'' if value=='__sin__' else value}) if value else qs

@transaction.atomic
def propagar_regimen(obj,user,antes):
    from .audit import registrar,snapshot
    if antes is not None and antes.get('regimen_laboral','')==obj.regimen_laboral: return
    if isinstance(obj,Trabajador):
        peers=CuentaVacacion.objects.filter(trabajador=obj)
        if not peers.exists() and obj.dni and Trabajador.objects.filter(dni=obj.dni).count()==1:
            peers=CuentaVacacion.objects.filter(dni=obj.dni,trabajador__isnull=True)
    elif isinstance(obj,CuentaVacacion):
        peers=Trabajador.objects.filter(pk=obj.trabajador_id) if obj.trabajador_id else Trabajador.objects.filter(dni=obj.dni)
        if peers.count()!=1:return
    else:return
    for peer in peers.select_for_update().exclude(regimen_laboral=obj.regimen_laboral):
        if antes is None and not obj.regimen_laboral:
            prior=snapshot(obj)
            type(obj).objects.filter(pk=obj.pk).update(regimen_laboral=peer.regimen_laboral,updated_at=timezone.now())
            obj.refresh_from_db();registrar(obj,user,'heredar_regimen',prior)
            return
        prior=snapshot(peer)
        type(peer).objects.filter(pk=peer.pk).update(regimen_laboral=obj.regimen_laboral,updated_at=timezone.now())
        peer.refresh_from_db();registrar(peer,user,'actualizar_regimen',prior)
