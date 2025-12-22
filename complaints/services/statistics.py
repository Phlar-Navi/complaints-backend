from django.db.models import Count, Q, Avg, F, ExpressionWrapper, fields
from django.utils import timezone
from datetime import timedelta, datetime
from complaints.models import Complaint, SLAConfig, ComplaintHistory


class ComplaintStatisticsService:
    """Service pour calculer les statistiques des plaintes"""
    
    def __init__(self, tenant=None, user=None):
        self.tenant = tenant
        self.user = user
    
    def get_dashboard_stats(self):
        """Retourne toutes les stats pour le dashboard"""
        now = timezone.now()
        week_start = now - timedelta(days=7)
        
        return {
            'overview': self.get_overview_stats(),
            'weekly_trend': self.get_weekly_trend(),
            'urgency_distribution': self.get_urgency_distribution(),
            'status_distribution': self.get_status_distribution(),
            'workload': self.get_agent_workload(),
            'sla_performance': self.get_sla_performance(),
            'personal_stats': self.get_personal_stats() if self.user else None,
        }
    
    def get_overview_stats(self):
        """Statistiques générales"""
        base_qs = Complaint.objects.filter(tenant=self.tenant)
        now = timezone.now()
        
        total = base_qs.count()
        
        # Cette semaine
        week_start = now - timedelta(days=7)
        this_week = base_qs.filter(submitted_at__gte=week_start).count()
        
        # Semaine précédente
        prev_week_start = week_start - timedelta(days=7)
        prev_week = base_qs.filter(
            submitted_at__gte=prev_week_start,
            submitted_at__lt=week_start
        ).count()
        
        # Calcul de la tendance
        if prev_week > 0:
            trend_percentage = ((this_week - prev_week) / prev_week) * 100
        else:
            trend_percentage = 100 if this_week > 0 else 0
        
        return {
            'total_complaints': total,
            'this_week': this_week,
            'prev_week': prev_week,
            'trend': 'up' if trend_percentage > 0 else 'down',
            'trend_percentage': abs(round(trend_percentage, 1)),
            'urgent_unhandled': base_qs.filter(
                urgency='HIGH',
                status__in=['NEW', 'RECEIVED']
            ).count(),
            'unassigned': base_qs.filter(assigned_user__isnull=True).count(),
            'assigned': base_qs.filter(assigned_user__isnull=False).count(),
            'overdue': base_qs.filter(
                sla_deadline__lt=now,
                status__in=['NEW', 'RECEIVED', 'ASSIGNED', 'IN_PROGRESS', 'INVESTIGATION', 'ACTION']
            ).count(),
        }
    
    def get_weekly_trend(self):
        """Tendance des plaintes sur les 7 derniers jours"""
        now = timezone.now()
        days_data = []
        
        for i in range(7):
            day = now - timedelta(days=6-i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            count = Complaint.objects.filter(
                tenant=self.tenant,
                submitted_at__gte=day_start,
                submitted_at__lt=day_end
            ).count()
            
            days_data.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'day': day_start.strftime('%A'),
                'count': count
            })
        
        return days_data
    
    def get_urgency_distribution(self):
        """Répartition par urgence"""
        base_qs = Complaint.objects.filter(tenant=self.tenant)
        total = base_qs.count()
        
        if total == 0:
            return {
                'HIGH': {'count': 0, 'percentage': 0},
                'MEDIUM': {'count': 0, 'percentage': 0},
                'LOW': {'count': 0, 'percentage': 0},
            }
        
        urgency_counts = base_qs.values('urgency').annotate(count=Count('id'))
        
        result = {}
        for item in urgency_counts:
            result[item['urgency']] = {
                'count': item['count'],
                'percentage': round((item['count'] / total) * 100, 1)
            }
        
        # Assurer que toutes les urgences sont présentes
        for urgency in ['HIGH', 'MEDIUM', 'LOW']:
            if urgency not in result:
                result[urgency] = {'count': 0, 'percentage': 0}
        
        return result
    
    def get_status_distribution(self):
        """Répartition par statut"""
        base_qs = Complaint.objects.filter(tenant=self.tenant)
        
        status_groups = {
            'to_handle': base_qs.filter(status__in=['NEW', 'RECEIVED']).count(),
            'in_progress': base_qs.filter(
                status__in=['ASSIGNED', 'IN_PROGRESS', 'INVESTIGATION', 'ACTION']
            ).count(),
            'closed': base_qs.filter(status='CLOSED').count(),
            'archived': base_qs.filter(status='ARCHIVED').count(),
        }
        
        total = sum(status_groups.values())
        
        # Ajouter les pourcentages
        if total > 0:
            for key in status_groups:
                count = status_groups[key]
                status_groups[key] = {
                    'count': count,
                    'percentage': round((count / total) * 100, 1)
                }
        
        return status_groups
    
    def get_agent_workload(self):
        """Charge de travail par agent"""
        from users.models import CustomUser
        
        agents = CustomUser.objects.filter(
            tenant=self.tenant,
            role__in=['AGENT', 'TENANT_ADMIN']
        )
        
        workload_data = []
        
        for agent in agents:
            assigned_count = Complaint.objects.filter(
                tenant=self.tenant,
                assigned_user=agent,
                status__in=['ASSIGNED', 'IN_PROGRESS', 'INVESTIGATION', 'ACTION']
            ).count()
            
            overdue_count = Complaint.objects.filter(
                tenant=self.tenant,
                assigned_user=agent,
                sla_deadline__lt=timezone.now(),
                status__in=['ASSIGNED', 'IN_PROGRESS', 'INVESTIGATION', 'ACTION']
            ).count()
            
            workload_data.append({
                'agent_id': str(agent.id),
                'agent_name': agent.full_name,
                'agent_email': agent.email,
                'assigned_count': assigned_count,
                'overdue_count': overdue_count,
            })
        
        # Trier par charge de travail
        workload_data.sort(key=lambda x: x['assigned_count'], reverse=True)
        
        return workload_data
    
    def get_sla_performance(self):
        """Performance SLA du tenant"""
        base_qs = Complaint.objects.filter(
            tenant=self.tenant,
            status__in=['RESOLVED', 'CLOSED']
        )
        
        total_resolved = base_qs.count()
        
        if total_resolved == 0:
            return {
                'total_resolved': 0,
                'sla_met': 0,
                'sla_missed': 0,
                'sla_met_percentage': 0,
                'sla_missed_percentage': 0,
            }
        
        # SLA respecté : closed_at <= sla_deadline
        sla_met = base_qs.filter(closed_at__lte=F('sla_deadline')).count()
        sla_missed = total_resolved - sla_met
        
        return {
            'total_resolved': total_resolved,
            'sla_met': sla_met,
            'sla_missed': sla_missed,
            'sla_met_percentage': round((sla_met / total_resolved) * 100, 1),
            'sla_missed_percentage': round((sla_missed / total_resolved) * 100, 1),
        }
    
    def get_personal_stats(self):
        """Statistiques personnelles de l'agent connecté"""
        if not self.user:
            return None
        
        # Plaintes assignées à l'utilisateur
        assigned_qs = Complaint.objects.filter(
            tenant=self.tenant,
            assigned_user=self.user
        )
        
        # Plaintes actives
        active_count = assigned_qs.filter(
            status__in=['ASSIGNED', 'IN_PROGRESS', 'INVESTIGATION', 'ACTION']
        ).count()
        
        # Plaintes résolues
        resolved_qs = assigned_qs.filter(status__in=['RESOLVED', 'CLOSED'])
        resolved_count = resolved_qs.count()
        
        # Temps moyen de résolution
        avg_resolution_time = None
        if resolved_count > 0:
            # Calculer la différence en heures
            resolved_complaints = resolved_qs.filter(closed_at__isnull=False)
            
            total_hours = 0
            count = 0
            for complaint in resolved_complaints:
                if complaint.resolution_time:
                    total_hours += complaint.resolution_time
                    count += 1
            
            if count > 0:
                avg_resolution_time = round(total_hours / count, 1)
        
        # Plaintes en retard
        overdue_count = assigned_qs.filter(
            sla_deadline__lt=timezone.now(),
            status__in=['ASSIGNED', 'IN_PROGRESS', 'INVESTIGATION', 'ACTION']
        ).count()
        
        return {
            'active_complaints': active_count,
            'resolved_complaints': resolved_count,
            'overdue_complaints': overdue_count,
            'avg_resolution_time_hours': avg_resolution_time,
        }
    
    def get_global_platform_stats(self):
        """Statistiques globales de la plateforme (pour SUPER_ADMIN)"""
        from tenants.models import Tenant
        
        all_complaints = Complaint.objects.all()
        total_complaints = all_complaints.count()
        
        # Par tenant
        tenant_stats = []
        for tenant in Tenant.objects.filter(is_active=True):
            tenant_complaints = all_complaints.filter(tenant=tenant)
            resolved = tenant_complaints.filter(status__in=['RESOLVED', 'CLOSED'])
            
            sla_met = 0
            sla_missed = 0
            
            if resolved.exists():
                sla_met = resolved.filter(closed_at__lte=F('sla_deadline')).count()
                sla_missed = resolved.count() - sla_met
            
            tenant_stats.append({
                'tenant_id': str(tenant.id),
                'tenant_name': tenant.name,
                'total_complaints': tenant_complaints.count(),
                'sla_met': sla_met,
                'sla_missed': sla_missed,
                'sla_met_percentage': round((sla_met / resolved.count()) * 100, 1) if resolved.exists() else 0,
            })
        
        # Volume par mois (12 derniers mois)
        monthly_volume = []
        now = timezone.now()
        
        for i in range(12):
            month_start = (now - timedelta(days=30*i)).replace(day=1, hour=0, minute=0, second=0)
            if i == 0:
                month_end = now
            else:
                month_end = month_start.replace(day=28) + timedelta(days=4)
                month_end = month_end.replace(day=1) - timedelta(days=1)
            
            count = all_complaints.filter(
                submitted_at__gte=month_start,
                submitted_at__lte=month_end
            ).count()
            
            monthly_volume.append({
                'month': month_start.strftime('%Y-%m'),
                'count': count
            })
        
        monthly_volume.reverse()
        
        # SLA global
        all_resolved = all_complaints.filter(status__in=['RESOLVED', 'CLOSED'])
        total_resolved = all_resolved.count()
        
        if total_resolved > 0:
            global_sla_met = all_resolved.filter(closed_at__lte=F('sla_deadline')).count()
            global_sla_percentage = round((global_sla_met / total_resolved) * 100, 1)
        else:
            global_sla_percentage = 0
        
        return {
            'total_complaints': total_complaints,
            'tenant_stats': tenant_stats,
            'monthly_volume': monthly_volume,
            'global_sla_percentage': global_sla_percentage,
        }