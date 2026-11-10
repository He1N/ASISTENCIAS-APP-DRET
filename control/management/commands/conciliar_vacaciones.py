from collections import Counter
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from control.models import Justificacion
from control.vacaciones_sync import plan_historico, sincronizar


class Command(BaseCommand):
    help='Previsualiza o enlaza vacaciones históricas de un periodo sin duplicar ni sustituir ajustes.'
    def add_arguments(self,parser):
        parser.add_argument('--periodo',type=int,required=True)
        parser.add_argument('--confirmar',action='store_true')
        parser.add_argument('--usuario')
    @transaction.atomic
    def handle(self,*args,**opts):
        user=None
        if opts['confirmar']:
            user=get_user_model().objects.filter(username=opts['usuario'],is_active=True).first()
            if not user or not user.has_perm('control.change_cuentavacacion'):
                raise CommandError('Indique un usuario activo autorizado para editar el control.')
        counts=Counter()
        qs=Justificacion.objects.filter(periodo_id=opts['periodo'],anulada=False,
            tipo_operacion__grupo_especial='VACACIONES').select_related('trabajador','tipo_operacion').order_by('pk')
        if opts['confirmar']: qs=qs.select_for_update(of=('self',))
        for j in qs:
            if opts['confirmar']: status=sincronizar(j,historico=True,usuario=user).estado
            else: status=plan_historico(j)['estado']
            counts[status]+=1
        self.stdout.write(('Confirmado' if opts['confirmar'] else 'Previsualización')+': '+str(dict(counts)))
