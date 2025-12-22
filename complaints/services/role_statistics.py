"""
Service pour gérer les statistiques selon le rôle de l'utilisateur
"""
from django.db.models import Count, Q, Avg, F, ExpressionWrapper, fields
from django.utils import timezone
from datetime import timedelta, datetime
from complaints.models import Complaint, SLAConfig, ComplaintHistory
from users.models import CustomUser


class RoleBasedStatisticsService:
    """Service pour calculer les statistiques adaptées au rôle"""
    
    def __init__(self, user, tenant=None):
        self.user = user
        self.tenant = tenant or user.tenant
        self.role = user.role
    
    def get_dashboard_stats(self):
        """Point d'entrée principal - retourne les stats selon le rôle"""
        
        role_methods = {
            'SUPER_ADMIN': self.get_super_admin_stats,
            'TENANT_ADMIN': self.get_tenant_admin_stats,
            'RECEPTION': self.get_reception_stats,
            'AGENT': self.get_agent_stats,
            'AUDITOR': self.get_auditor_stats,
        }
        
        method = role_methods.get(self.role, self.get_agent_stats)
        return {
            'role': self.role,
            'user': {
                'id': str(self.user.id),
                'name': self.user.full_name,
                'email': self.user.email,
            },
            'stats': method(),
            'timestamp': timezone.now().isoformat(),
        }
    
    # ============================================================
    # SUPER_ADMIN - Vue Plateforme Globale
    # ============================================================
    def get_super_admin_stats(self):
        """Statistiques pour SUPER_ADMIN - Vue multi-tenants"""
        from tenants.models import Tenant
        
        all_complaints = Complaint.objects.all()
        total_complaints = all_complaints.count()
        
        # Stats par tenant
        active_tenants = Tenant.objects.filter(is_active=True)
        tenant_stats = []
        
        for tenant in active_tenants:
            tenant_complaints = all_complaints.filter(tenant=tenant)
            resolved = tenant_complaints.filter(status__in=['RESOLVED', 'CLOSED'])
            
            sla_met = 0
            if resolved.exists():
                sla_met = resolved.filter(closed_at__lte=F('sla_deadline')).count()
            
            tenant_stats.append({
                'tenant_id': str(tenant.id),
                'tenant_name': tenant.name,
                'schema_name': tenant.schema_name,
                'total_complaints': tenant_complaints.count(),
                'active_complaints': tenant_complaints.exclude(
                    status__in=['RESOLVED', 'CLOSED', 'ARCHIVED']
                ).count(),
                'sla_compliance_rate': round((sla_met / resolved.count()) * 100, 1) if resolved.exists() else 0,
                'overdue': tenant_complaints.filter(
                    sla_deadline__lt=timezone.now(),
                    status__in=['NEW', 'RECEIVED', 'ASSIGNED', 'IN_PROGRESS']
                ).count(),
                'is_premium': tenant.is_premium,
            })
        
        # Trier par nombre de plaintes
        tenant_stats.sort(key=lambda x: x['total_complaints'], reverse=True)
        
        # Volume mensuel (12 mois)
        monthly_volume = self._get_monthly_volume(all_complaints)
        
        # SLA global
        all_resolved = all_complaints.filter(status__in=['RESOLVED', 'CLOSED'])
        total_resolved = all_resolved.count()
        global_sla_met = 0
        
        if total_resolved > 0:
            global_sla_met = all_resolved.filter(closed_at__lte=F('sla_deadline')).count()
        
        return {
            'platform_overview': {
                'total_tenants': active_tenants.count(),
                'total_complaints': total_complaints,
                'total_active_complaints': all_complaints.exclude(
                    status__in=['RESOLVED', 'CLOSED', 'ARCHIVED']
                ).count(),
                'global_sla_compliance': round((global_sla_met / total_resolved) * 100, 1) if total_resolved > 0 else 0,
            },
            'tenant_stats': tenant_stats[:10],  # Top 10
            'monthly_volume': monthly_volume,
            'alerts': self._get_platform_alerts(tenant_stats),
        }
    
    # ============================================================
    # TENANT_ADMIN - Vue Complète du Tenant
    # ============================================================
    def get_tenant_admin_stats(self):
        """Statistiques pour TENANT_ADMIN - Vue complète"""
        base_qs = Complaint.objects.filter(tenant=self.tenant)
        
        # Vue d'ensemble
        overview = self._get_tenant_overview(base_qs)
        
        # Performance d'équipe
        team_performance = self._get_team_performance()
        
        # Tendances
        trends = {
            'weekly': self._get_weekly_trend(base_qs),
            'urgency_distribution': self._get_urgency_distribution(base_qs),
            'status_distribution': self._get_status_distribution(base_qs),
            'category_stats': self._get_category_stats(base_qs),
        }
        
        # Alertes
        alerts = self._get_tenant_alerts(base_qs)
        
        return {
            'overview': overview,
            'team_performance': team_performance,
            'trends': trends,
            'alerts': alerts,
            'sla_performance': self._get_sla_performance(base_qs),
        }
    
    # ============================================================
    # RECEPTION - Vue Triage et Assignation
    # ============================================================
    def get_reception_stats(self):
        """Statistiques pour RECEPTION - Focus assignation"""
        base_qs = Complaint.objects.filter(tenant=self.tenant)
        today = timezone.now().date()
        
        # Stats du jour
        today_complaints = base_qs.filter(submitted_at__date=today)
        
        # Plaintes créées par moi
        my_created = base_qs.filter(submitted_by=self.user)
        my_created_today = my_created.filter(submitted_at__date=today)
        
        # Stats d'assignation
        unassigned = base_qs.filter(assigned_user__isnull=True)
        unassigned_by_urgency = {
            'HIGH': unassigned.filter(urgency='HIGH').count(),
            'MEDIUM': unassigned.filter(urgency='MEDIUM').count(),
            'LOW': unassigned.filter(urgency='LOW').count(),
        }
        
        # Agents disponibles avec leur charge
        agents_workload = self._get_agents_availability()
        
        # Performance personnelle
        this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        my_created_this_month = my_created.filter(submitted_at__gte=this_month_start)
        
        return {
            'today_stats': {
                'total_received': today_complaints.count(),
                'created_by_me': my_created_today.count(),
                'pending_assignment': unassigned.count(),
                'urgent_unassigned': unassigned.filter(urgency='HIGH').count(),
            },
            'assignment_queue': {
                'unassigned_by_urgency': unassigned_by_urgency,
                'agents_availability': agents_workload,
            },
            'personal_performance': {
                'total_created_this_month': my_created_this_month.count(),
                'average_per_day': round(my_created_this_month.count() / max(timezone.now().day, 1), 1),
                'by_category': list(
                    my_created_this_month.values('category__name')
                    .annotate(count=Count('id'))
                    .order_by('-count')[:5]
                ),
            },
            'quick_actions': {
                'urgent_to_assign': list(
                    unassigned.filter(urgency='HIGH')
                    .values('id', 'reference', 'title', 'submitted_at')[:5]
                ),
            }
        }
    
    # ============================================================
    # AGENT - Vue Mes Tâches
    # ============================================================
    def get_agent_stats(self):
        """Statistiques pour AGENT - Mes plaintes uniquement"""
        my_complaints = Complaint.objects.filter(
            tenant=self.tenant,
            assigned_user=self.user
        )
        
        # Plaintes actives
        active = my_complaints.exclude(status__in=['RESOLVED', 'CLOSED', 'ARCHIVED'])
        
        # Urgentes
        urgent = active.filter(urgency='HIGH')
        
        # En retard
        overdue = active.filter(sla_deadline__lt=timezone.now())
        
        # Résolues cette semaine
        week_start = timezone.now() - timedelta(days=7)
        resolved_this_week = my_complaints.filter(
            status__in=['RESOLVED', 'CLOSED'],
            closed_at__gte=week_start
        )
        
        # Performance personnelle
        personal_perf = self._get_agent_personal_performance(my_complaints)
        
        # Charge de travail par statut
        workload_by_status = dict(
            active.values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )
        
        # Prochaines échéances
        upcoming_deadlines = list(
            active.filter(sla_deadline__isnull=False)
            .order_by('sla_deadline')
            .values('id', 'reference', 'title', 'sla_deadline', 'urgency')[:5]
        )
        
        return {
            'my_complaints': {
                'active': active.count(),
                'urgent': urgent.count(),
                'overdue': overdue.count(),
                'resolved_this_week': resolved_this_week.count(),
            },
            'personal_performance': personal_perf,
            'workload_by_status': workload_by_status,
            'upcoming_deadlines': upcoming_deadlines,
            'weekly_trend': self._get_weekly_trend(my_complaints),
            'quick_actions': {
                'urgent_tasks': list(
                    urgent.values('id', 'reference', 'title', 'sla_deadline')[:5]
                ),
                'overdue_tasks': list(
                    overdue.values('id', 'reference', 'title', 'sla_deadline')[:5]
                ),
            }
        }
    
    # ============================================================
    # AUDITOR - Vue Contrôle et Audit
    # ============================================================
    def get_auditor_stats(self):
        """Statistiques pour AUDITOR - Focus conformité"""
        base_qs = Complaint.objects.filter(tenant=self.tenant)
        
        # Indicateurs de conformité
        compliance = self._get_compliance_indicators(base_qs)
        
        # Analyse qualité
        quality = self._get_quality_analysis(base_qs)
        
        # Audit trail récent
        recent_history = ComplaintHistory.objects.filter(
            tenant=self.tenant
        ).order_by('-created_at')[:20]
        
        audit_trail = [
            {
                'id': str(h.id),
                'complaint_reference': h.complaint_reference,
                'action': h.action,
                'user': h.user.full_name if h.user else 'System',
                'description': h.description,
                'timestamp': h.created_at.isoformat(),
            }
            for h in recent_history
        ]
        
        return {
            'compliance_indicators': compliance,
            'quality_analysis': quality,
            'audit_trail': audit_trail,
            'sla_performance': self._get_sla_performance(base_qs),
            'agent_performance': self._get_team_performance(),
        }
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def _get_tenant_overview(self, qs):
        """Vue d'ensemble tenant"""
        now = timezone.now()
        today = now.date()
        week_start = now - timedelta(days=7)
        
        return {
            'total_complaints': qs.count(),
            'today': qs.filter(submitted_at__date=today).count(),
            'this_week': qs.filter(submitted_at__gte=week_start).count(),
            'urgent_unhandled': qs.filter(
                urgency='HIGH',
                status__in=['NEW', 'RECEIVED']
            ).count(),
            'unassigned': qs.filter(assigned_user__isnull=True).count(),
            'overdue': qs.filter(
                sla_deadline__lt=now,
                status__in=['NEW', 'RECEIVED', 'ASSIGNED', 'IN_PROGRESS', 'INVESTIGATION', 'ACTION']
            ).count(),
        }
    
    def _get_team_performance(self):
        """Performance de l'équipe"""
        agents = CustomUser.objects.filter(
            tenant=self.tenant,
            role__in=['AGENT', 'TENANT_ADMIN'],
            is_active=True
        )
        
        team_data = []
        for agent in agents:
            assigned = Complaint.objects.filter(
                tenant=self.tenant,
                assigned_user=agent
            )
            
            active = assigned.exclude(status__in=['RESOLVED', 'CLOSED', 'ARCHIVED'])
            resolved = assigned.filter(status__in=['RESOLVED', 'CLOSED'])
            
            # SLA compliance
            sla_met = 0
            if resolved.exists():
                sla_met = resolved.filter(closed_at__lte=F('sla_deadline')).count()
            
            # Temps moyen de résolution
            avg_time = None
            if resolved.exists():
                times = [c.resolution_time for c in resolved if c.resolution_time]
                if times:
                    avg_time = round(sum(times) / len(times), 1)
            
            team_data.append({
                'agent_id': str(agent.id),
                'agent_name': agent.full_name,
                'active_complaints': active.count(),
                'resolved_complaints': resolved.count(),
                'sla_compliance_rate': round((sla_met / resolved.count()) * 100, 1) if resolved.exists() else 0,
                'avg_resolution_time_hours': avg_time,
                'overdue': active.filter(sla_deadline__lt=timezone.now()).count(),
            })
        
        return sorted(team_data, key=lambda x: x['active_complaints'], reverse=True)
    
    def _get_agents_availability(self):
        """Disponibilité des agents pour assignation"""
        agents = CustomUser.objects.filter(
            tenant=self.tenant,
            role__in=['AGENT', 'TENANT_ADMIN'],
            is_active=True
        )
        
        availability = []
        for agent in agents:
            active_count = Complaint.objects.filter(
                tenant=self.tenant,
                assigned_user=agent,
                status__in=['ASSIGNED', 'IN_PROGRESS', 'INVESTIGATION', 'ACTION']
            ).count()
            
            # Déterminer la disponibilité
            if active_count == 0:
                status = 'available'
            elif active_count < 5:
                status = 'light'
            elif active_count < 10:
                status = 'moderate'
            else:
                status = 'heavy'
            
            availability.append({
                'agent_id': str(agent.id),
                'agent_name': agent.full_name,
                'active_complaints': active_count,
                'status': status,
            })
        
        return sorted(availability, key=lambda x: x['active_complaints'])
    
    def _get_agent_personal_performance(self, qs):
        """Performance personnelle d'un agent"""
        resolved = qs.filter(status__in=['RESOLVED', 'CLOSED'])
        
        # Temps moyen de résolution
        avg_time = None
        if resolved.exists():
            times = [c.resolution_time for c in resolved if c.resolution_time]
            if times:
                avg_time = round(sum(times) / len(times), 1)
        
        # Taux SLA
        sla_met = 0
        if resolved.exists():
            sla_met = resolved.filter(closed_at__lte=F('sla_deadline')).count()
            sla_rate = round((sla_met / resolved.count()) * 100, 1)
        else:
            sla_rate = 0
        
        # Moyenne de l'équipe pour comparaison
        team_avg = self._get_team_average_resolution_time()
        
        return {
            'avg_resolution_time_hours': avg_time,
            'sla_compliance_rate': sla_rate,
            'total_resolved': resolved.count(),
            'comparison_with_team': {
                'team_avg_time': team_avg,
                'better_than_average': avg_time < team_avg if avg_time and team_avg else None,
            }
        }
    
    def _get_team_average_resolution_time(self):
        """Temps moyen de résolution de l'équipe"""
        resolved = Complaint.objects.filter(
            tenant=self.tenant,
            status__in=['RESOLVED', 'CLOSED']
        )
        
        times = [c.resolution_time for c in resolved if c.resolution_time]
        return round(sum(times) / len(times), 1) if times else None
    
    def _get_compliance_indicators(self, qs):
        """Indicateurs de conformité"""
        resolved = qs.filter(status__in=['RESOLVED', 'CLOSED'])
        sla_met = resolved.filter(closed_at__lte=F('sla_deadline')).count() if resolved.exists() else 0
        
        return {
            'sla_compliance_rate': round((sla_met / resolved.count()) * 100, 1) if resolved.exists() else 0,
            'overdue_complaints': qs.filter(
                sla_deadline__lt=timezone.now(),
                status__in=['NEW', 'RECEIVED', 'ASSIGNED', 'IN_PROGRESS']
            ).count(),
            'unassigned_complaints': qs.filter(assigned_user__isnull=True).count(),
            'complaints_without_activity': qs.filter(
                comments__isnull=True,
                status__in=['ASSIGNED', 'IN_PROGRESS']
            ).distinct().count(),
        }
    
    def _get_quality_analysis(self, qs):
        """Analyse qualité"""
        resolved = qs.filter(status__in=['RESOLVED', 'CLOSED'])
        
        # Distribution des temps
        if resolved.exists():
            times = [c.resolution_time for c in resolved if c.resolution_time]
            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
            else:
                avg_time = min_time = max_time = None
        else:
            avg_time = min_time = max_time = None
        
        return {
            'resolution_time_distribution': {
                'average': round(avg_time, 1) if avg_time else None,
                'min': round(min_time, 1) if min_time else None,
                'max': round(max_time, 1) if max_time else None,
            },
            'reopened_complaints': 0,  # À implémenter si nécessaire
            'critical_complaints': qs.filter(
                urgency='HIGH',
                status__in=['NEW', 'RECEIVED', 'ASSIGNED']
            ).count(),
        }
    
    def _get_weekly_trend(self, qs):
        """Tendance hebdomadaire"""
        now = timezone.now()
        days_data = []
        
        for i in range(7):
            day = now - timedelta(days=6-i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            count = qs.filter(
                submitted_at__gte=day_start,
                submitted_at__lt=day_end
            ).count()
            
            days_data.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'day': day_start.strftime('%a'),
                'count': count
            })
        
        return days_data
    
    def _get_urgency_distribution(self, qs):
        """Distribution par urgence"""
        total = qs.count()
        if total == 0:
            return {}
        
        dist = {}
        for urgency in ['HIGH', 'MEDIUM', 'LOW']:
            count = qs.filter(urgency=urgency).count()
            dist[urgency] = {
                'count': count,
                'percentage': round((count / total) * 100, 1)
            }
        
        return dist
    
    def _get_status_distribution(self, qs):
        """Distribution par statut"""
        return {
            'to_handle': qs.filter(status__in=['NEW', 'RECEIVED']).count(),
            'in_progress': qs.filter(status__in=['ASSIGNED', 'IN_PROGRESS', 'INVESTIGATION', 'ACTION']).count(),
            'closed': qs.filter(status='CLOSED').count(),
            'archived': qs.filter(status='ARCHIVED').count(),
        }
    
    def _get_category_stats(self, qs):
        """Stats par catégorie"""
        return list(
            qs.values('category__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
    
    def _get_sla_performance(self, qs):
        """Performance SLA"""
        resolved = qs.filter(status__in=['RESOLVED', 'CLOSED'])
        total = resolved.count()
        
        if total == 0:
            return {'sla_met': 0, 'sla_missed': 0, 'compliance_rate': 0}
        
        sla_met = resolved.filter(closed_at__lte=F('sla_deadline')).count()
        
        return {
            'sla_met': sla_met,
            'sla_missed': total - sla_met,
            'compliance_rate': round((sla_met / total) * 100, 1),
        }
    
    def _get_monthly_volume(self, qs):
        """Volume mensuel"""
        now = timezone.now()
        monthly = []
        
        for i in range(12):
            month_start = (now - timedelta(days=30*i)).replace(day=1, hour=0, minute=0, second=0)
            if i == 0:
                month_end = now
            else:
                month_end = month_start.replace(day=28) + timedelta(days=4)
                month_end = month_end.replace(day=1) - timedelta(days=1)
            
            count = qs.filter(
                submitted_at__gte=month_start,
                submitted_at__lte=month_end
            ).count()
            
            monthly.append({
                'month': month_start.strftime('%Y-%m'),
                'count': count
            })
        
        monthly.reverse()
        return monthly
    
    def _get_platform_alerts(self, tenant_stats):
        """Alertes plateforme"""
        alerts = []
        
        for t in tenant_stats:
            if t['sla_compliance_rate'] < 70:
                alerts.append({
                    'type': 'low_sla',
                    'severity': 'high',
                    'tenant': t['tenant_name'],
                    'message': f"SLA compliance is {t['sla_compliance_rate']}% (below 70%)",
                })
            
            if t['overdue'] > 5:
                alerts.append({
                    'type': 'many_overdue',
                    'severity': 'medium',
                    'tenant': t['tenant_name'],
                    'message': f"{t['overdue']} complaints are overdue",
                })
        
        return alerts[:10]  # Top 10 alertes
    
    def _get_tenant_alerts(self, qs):
        """Alertes tenant"""
        alerts = []
        now = timezone.now()
        
        # Urgentes non traitées
        urgent = qs.filter(urgency='HIGH', status__in=['NEW', 'RECEIVED']).count()
        if urgent > 0:
            alerts.append({
                'type': 'urgent_unhandled',
                'severity': 'high',
                'count': urgent,
                'message': f"{urgent} urgent complaint(s) need immediate attention",
            })
        
        # SLA proche expiration (< 2h)
        two_hours = now + timedelta(hours=2)
        soon_overdue = qs.filter(
            sla_deadline__lt=two_hours,
            sla_deadline__gt=now,
            status__in=['NEW', 'RECEIVED', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        
        if soon_overdue > 0:
            alerts.append({
                'type': 'sla_expiring_soon',
                'severity': 'medium',
                'count': soon_overdue,
                'message': f"{soon_overdue} complaint(s) will breach SLA in less than 2 hours",
            })
        
        return alerts