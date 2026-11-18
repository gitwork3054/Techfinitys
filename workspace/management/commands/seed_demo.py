from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from workspace.models import (ClientAccount, Member, ClientAssignment, Project, Task, Update, Note, CalendarEvent, Record,
    Attendance, LeaveRequest, TimeEntry, ApprovalRequest, SupportTicket, TicketMessage, ProjectMilestone, SavedView, Lead)
from workspace.seed_data import seed_rows

class Command(BaseCommand):
    help='Seed a complete local Techfinitys CRM hierarchy and sample workflow.'

    def handle(self,*args,**kwargs):
        if not settings.DEBUG:
            raise CommandError('Refusing to create demo accounts in production. Use bootstrap_admin instead.')
        admin_user,_=User.objects.get_or_create(username='admin',defaults={'email':'admin@techfinitys.local','is_staff':True,'is_superuser':True})
        admin_user.is_staff=True; admin_user.is_superuser=True; admin_user.set_password('admin12345'); admin_user.save()
        admin,_=Member.objects.update_or_create(user=admin_user,defaults={'role':'admin','department':'Management','job_title':'Super Admin','client':'','permissions':[]})

        manager_user,_=User.objects.get_or_create(username='manager',defaults={'email':'manager@techfinitys.local'})
        manager_user.set_password('manager12345'); manager_user.first_name='Maya'; manager_user.last_name='Shah'; manager_user.save()
        manager,_=Member.objects.update_or_create(user=manager_user,defaults={'role':'manager','manager':admin,'department':'Operations','job_title':'Office Manager','client':'','permissions':[]})

        clients=[]
        for code,name,company,pkg in [
            ('aurelia-living','Aurelia Living','Aurelia Living Pvt Ltd','Growth Studio'),
            ('northstar-foods','Northstar Foods','Northstar Foods','Social + Performance'),
            ('velora-home','Velora Home','Velora Home Decor','Content Retainer'),
        ]:
            c,_=ClientAccount.objects.update_or_create(code=code,defaults={'name':name,'company':company,'package':pkg,'status':'active','created_by':admin_user,'email':f'hello@{code}.local'})
            clients.append(c)

        employees=[]
        for username,first,last,job,dept in [
            ('aarav','Aarav','Patel','Account Executive','Client Success'),
            ('riya','Riya','Mehta','Content Strategist','Content'),
            ('dev','Dev','Shah','Designer','Creative'),
            ('neha','Neha','Joshi','Performance Marketer','Performance'),
        ]:
            u,_=User.objects.get_or_create(username=username,defaults={'email':f'{username}@techfinitys.local'})
            u.set_password('employee12345'); u.first_name=first; u.last_name=last; u.save()
            m,_=Member.objects.update_or_create(user=u,defaults={'role':'employee','manager':manager,'department':dept,'job_title':job,'client':'','permissions':[]})
            employees.append(m)

        assignments=[(clients[0],employees[0],True),(clients[0],employees[1],False),(clients[0],employees[2],False),(clients[0],employees[3],False),(clients[1],employees[0],True),(clients[1],employees[3],False),(clients[2],employees[1],True),(clients[2],employees[2],False)]
        for c,e,primary in assignments:
            ClientAssignment.objects.update_or_create(client=c,employee=e,defaults={'assigned_by':manager,'role_title':'Primary owner' if primary else e.job_title,'is_primary':primary,'active':True})

        cu,_=User.objects.get_or_create(username='client_aurelia',defaults={'email':'client@aurelia.local'})
        cu.set_password('client12345'); cu.first_name='Meera'; cu.last_name='Aurelia'; cu.save()
        Member.objects.update_or_create(user=cu,defaults={'role':'client','client_account':clients[0],'client':clients[0].code,'job_title':'Client portal','permissions':[]})

        project,_=Project.objects.update_or_create(client=clients[0],title='October Growth Campaign',defaults={'description':'Monthly social, design and performance delivery.','status':'active','manager':manager,'owner':employees[0],'progress':45,'created_by':manager,'start_date':timezone.localdate(),'due_date':timezone.localdate()+timedelta(days=30)})
        task_specs=[
            ('October content plan','completed',employees[1],100,True),
            ('Product carousel design','review',employees[2],70,True),
            ('Meta campaign optimisation','in_progress',employees[3],55,False),
            ('Client monthly review','todo',employees[0],0,True),
        ]
        for title,status,assignee,progress,visible in task_specs:
            t,_=Task.objects.update_or_create(client=clients[0],project=project,title=title,defaults={'status':status,'priority':'high' if status in ('review','in_progress') else 'normal','assigned_to':assignee,'created_by':manager,'due_at':timezone.now()+timedelta(days=7),'client_visible':visible,'estimated_hours':4})
            Update.objects.get_or_create(client=clients[0],task=t,title=f'{title} update',defaults={'author':assignee,'body':f'Progress is moving on {title.lower()}.','visibility':'client' if visible else 'team','progress':progress})
        Note.objects.get_or_create(client=clients[0],author=manager,body='Keep the visual direction premium and minimal. Client prefers concise copy.',defaults={'visibility':'team','pinned':True,'project':project})
        CalendarEvent.objects.get_or_create(client=clients[0],title='Monthly client review',defaults={'event_type':'meeting','description':'Review delivery, approvals and next month priorities.','start_at':timezone.now()+timedelta(days=5),'end_at':timezone.now()+timedelta(days=5,hours=1),'owner':manager,'created_by':manager})

        # Retain the original modules with live data scoped to the first client.
        for row in seed_rows():
            row=dict(row)
            row['client']=clients[0].code if row.get('client') in ('c1','') else row.get('client')
            Record.objects.update_or_create(id=f'live:{row["id"]}',defaults={'space':'live','kind':row['kind'],'client':row['client'],'data':row})

        # Enterprise operations fixtures. Safe to re-run without duplicated business rows.
        product_task = Task.objects.filter(client=clients[0], title='Product carousel design').first()
        for idx, employee in enumerate(employees[:3]):
            Attendance.objects.get_or_create(employee=employee,date=timezone.localdate(),defaults={
                'clock_in':timezone.now()-timedelta(hours=idx+2),
                'clock_out':timezone.now()-timedelta(minutes=15) if idx==1 else None,
                'mode':['office','remote','field'][idx],
                'break_seconds':900 if idx==1 else 0,
            })
        LeaveRequest.objects.get_or_create(employee=employees[1],
            start_date=timezone.localdate()+timedelta(days=10),end_date=timezone.localdate()+timedelta(days=12),
            defaults={'leave_type':'annual','reason':'Planned time off','status':'pending'})
        TimeEntry.objects.get_or_create(employee=employees[2],client=clients[0],task=product_task,
            date=timezone.localdate(), description='Carousel creative production',
            defaults={'project':project,'minutes':180,'status':'submitted','billable':True})
        TimeEntry.objects.get_or_create(employee=employees[1],client=clients[0],
            date=timezone.localdate()-timedelta(days=1),description='Content calendar strategy',
            defaults={'project':project,'minutes':240,'status':'approved','billable':True,'reviewed_by':manager,'reviewed_at':timezone.now()})
        ApprovalRequest.objects.get_or_create(client=clients[0],title='November campaign creative approval',
            defaults={'project':project,'task':product_task,'audience':'client','requested_by':employees[2],
                      'description':'Please review the visual approach and approve the carousel before scheduling.',
                      'due_at':timezone.now()+timedelta(days=4)})
        ApprovalRequest.objects.get_or_create(client=clients[0],title='Internal campaign QA',
            defaults={'project':project,'audience':'internal','requested_by':employees[1], 'reviewer':manager,
                      'description':'Check copy, visual consistency and tracking links.'})
        ticket,_=SupportTicket.objects.get_or_create(client=clients[0],title='Update seasonal launch offer',
            defaults={'created_by':Member.objects.get(user=cu),'description':'Please update the seasonal offer across the next social creatives.',
                      'priority':'high','status':'open','assigned_to':employees[0]})
        TicketMessage.objects.get_or_create(ticket=ticket,author=employees[0],body='Thanks — we are checking the revised copy.',defaults={'internal':False})
        for name,days,status in [('Discovery & strategy',2,'completed'),('Creative production',10,'active'),('Client sign-off',18,'planned'),('Launch & reporting',29,'planned')]:
            ProjectMilestone.objects.get_or_create(project=project,title=name,defaults={
                'due_date':timezone.localdate()+timedelta(days=days),'status':status,'owner':employees[0],'client_visible':True})
        for name,company,stage,value,source in [
            ('Anika Rao','Nexus Studio','proposal',72000,'Website inquiry'),
            ('Shiv Patel','Bluebird Foods','qualified',45000,'Referral'),
            ('Rohan Mehta','Summit Collective','contacted',30000,'LinkedIn'),
            ('Kavya Shah','Luma Wellness','negotiation',110000,'Instagram'),
        ]:
            Lead.objects.get_or_create(name=name,company=company,defaults={'stage':stage,'estimated_value':value,'source':source,'owner':manager})
        SavedView.objects.get_or_create(owner=employees[0],module='tasks',name='My urgent work',defaults={
            'filters':{'status':'open','owner':str(employees[0].id),'priority':'high','timespan':'all','client':'','search':'','view':'list'}})

        self.stdout.write(self.style.SUCCESS('Full CRM demo seeded. Logins: admin/admin12345, manager/manager12345, aarav/employee12345, client_aurelia/client12345'))
