"""Private employee messaging, profile photos and role-scoped recent projects.

Every chat query is scoped to ChatParticipant and clients are denied access.
"""
import io
import json
from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import (
    Member, Project, ClientAssignment, ChatConversation, ChatParticipant,
    ChatMessage, RecentProjectVisit, Notification,
)
from .views import _context, _client_ids_for, _log

STAFF = ('admin', 'manager', 'employee')


def _request_member(request):
    member = _context(request)
    if not request.user.is_active:
        raise PermissionError('This account is inactive')
    return member


def _json_post(request):
    try:
        value = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        raise ValueError('Send a valid JSON object')
    if not isinstance(value, dict):
        raise ValueError('Send a valid JSON object')
    return value


def _staff(member):
    if member.role not in STAFF:
        raise PermissionError('Internal team messaging is available to employees only')


def _person(m):
    return m.user.get_full_name() or m.user.username


def _photo(m):
    return f'/api/collaboration/avatar/{m.id}/' if m.profile_photo else ''


def _people(member):
    return Member.objects.filter(role__in=STAFF, is_active=True, user__is_active=True).select_related('user')


def _recent(member):
    # Visibility is enforced when reading, not just when recording the visit.
    visible = Project.objects.filter(client_id__in=_client_ids_for(member))
    visited_ids = list(RecentProjectVisit.objects.filter(member=member, project__in=visible)
                       .order_by('-visited_at').values_list('project_id', flat=True)[:18])
    ordered = list(visible.filter(pk__in=visited_ids).select_related('client'))
    indexed = {p.id: p for p in ordered}
    ordered = [indexed[pk] for pk in visited_ids if pk in indexed]
    if len(ordered) < 14:
        ordered.extend(visible.exclude(pk__in=visited_ids).select_related('client').order_by('-updated_at')[:14-len(ordered)])
    return [
        {'id':str(p.pk), 'name':p.title, 'clientName':p.client.name, 'status':p.status,
         'progress':p.progress, 'code':f'TF-{str(p.id)[:6].upper()}'}
        for p in ordered[:18]
    ]


def _is_chat_member(member, chat_id):
    conv = ChatConversation.objects.filter(pk=chat_id, participants__member=member).first()
    if conv is None:
        raise PermissionError('Conversation is not available')
    return conv


def _summary(c, actor):
    participants = list(c.participants.all())
    peers = [p.member for p in participants if p.member_id != actor.id]
    title = c.title if c.kind == 'group' else (_person(peers[0]) if peers else 'Direct message')
    photo = _photo(peers[0]) if c.kind == 'direct' and peers else ''
    latest = c.messages.order_by('-created_at', '-id').first()
    participation = next((p for p in participants if p.member_id == actor.id), None)
    unread = c.messages.exclude(sender=actor)
    if participation and participation.last_read_at:
        unread = unread.filter(created_at__gt=participation.last_read_at)
    return {
        'id':str(c.id), 'kind':c.kind, 'title':title, 'photo':photo,
        'people':[{'id':p.member_id,'name':_person(p.member),'photo':_photo(p.member)} for p in participants],
        'lastMessage':latest.body[:150] if latest else '',
        'lastAt':(latest.created_at if latest else c.created_at).isoformat(),
        'unread':unread.count(),
        'createdBy':c.created_by_id,
    }


def _message(m):
    return {
        'id':str(m.pk), 'body':m.body, 'senderId':m.sender_id,
        'senderName':_person(m.sender), 'photo':_photo(m.sender),
        'at':m.created_at.isoformat(),
    }


@require_http_methods(['GET','POST'])
def collaboration_api(request):
    try:
        actor = _request_member(request)
        if request.method == 'GET':
            result = {'recentProjects':_recent(actor), 'chatEnabled':actor.role in STAFF}
            if actor.role in STAFF:
                convs = (ChatConversation.objects.filter(participants__member=actor)
                    .prefetch_related(Prefetch('participants',queryset=ChatParticipant.objects.select_related('member__user')))
                    .order_by('-updated_at')[:80])
                result['conversations'] = [_summary(c, actor) for c in convs]
                result['people'] = [
                    {'id':m.id,'name':_person(m),'title':m.job_title or m.get_role_display(),
                     'photo':_photo(m), 'department':m.department}
                    for m in _people(actor).exclude(pk=actor.pk)[:200]
                ]
            return JsonResponse(result)
        data = _json_post(request)
        action = str(data.get('action') or '')
        if action == 'visit_project':
            project = Project.objects.filter(pk=data.get('projectId'), client_id__in=_client_ids_for(actor)).first()
            if not project:
                raise PermissionError('Project is not accessible')
            RecentProjectVisit.objects.update_or_create(member=actor,project=project,defaults={})
            return JsonResponse({'ok':True,'recentProjects':_recent(actor)})
        _staff(actor)
        if action == 'start_chat':
            kind = data.get('kind')
            ids = data.get('memberIds', [])
            if not isinstance(ids, list):
                raise ValueError('Select team members')
            try:
                ids = {int(x) for x in ids}
            except (ValueError, TypeError):
                raise ValueError('Invalid team member')
            ids.discard(actor.id)
            if kind not in ('direct','group') or (kind == 'direct' and len(ids) != 1) or (kind == 'group' and not 1 <= len(ids) <= 19):
                raise ValueError('Select one person for direct messages or 1–19 for a group')
            if _people(actor).filter(pk__in=ids).count() != len(ids):
                raise PermissionError('You can only message active employees')
            title = str(data.get('title') or '').strip()
            if kind == 'group' and not (2 <= len(title) <= 100):
                raise ValueError('Group name must contain 2–100 characters')
            if kind == 'direct':
                key = ':'.join(str(x) for x in sorted(ids | {actor.id}))
                # Unique direct_key prevents duplicated private threads.
                created = False
                try:
                    with transaction.atomic():
                        convo, created = ChatConversation.objects.get_or_create(
                            direct_key=key, defaults={'kind':'direct','created_by':actor}
                        )
                        if created:
                            ChatParticipant.objects.bulk_create([
                                ChatParticipant(conversation=convo,member_id=i) for i in ids | {actor.id}
                            ])
                except IntegrityError:
                    convo = ChatConversation.objects.get(direct_key=key)
            else:
                with transaction.atomic():
                    convo = ChatConversation.objects.create(kind='group',title=title,created_by=actor)
                    ChatParticipant.objects.bulk_create([
                        ChatParticipant(conversation=convo,member_id=i) for i in ids | {actor.id}
                    ])
            if kind == 'group' or created:
                _log(actor, 'Started internal conversation', convo, detail='Group created' if kind == 'group' else 'Direct chat started (message contents private)')
            return JsonResponse({'ok':True,'conversation':_summary(convo,actor)})
        if action == 'send_chat':
            convo = _is_chat_member(actor, data.get('conversationId'))
            body = str(data.get('body') or '').strip()
            if not body or len(body) > 4000:
                raise ValueError('Message must contain 1–4000 characters')
            with transaction.atomic():
                message = ChatMessage.objects.create(conversation=convo,sender=actor,body=body)
                ChatConversation.objects.filter(pk=convo.pk).update(updated_at=message.created_at)
                ChatParticipant.objects.filter(conversation=convo,member=actor).update(last_read_at=message.created_at)
                _log(actor, 'Sent internal chat message', convo, detail='Team message sent (content is private)')
                # WorkChat popups use the same recipient-scoped notification feed
                # as other CRM alerts. Never notify the sender or nonparticipants.
                recipients = Member.objects.filter(
                    chat_memberships__conversation=convo,
                    is_active=True, user__is_active=True,
                ).exclude(pk=actor.pk).distinct()
                Notification.objects.bulk_create([
                    Notification(
                        recipient=recipient,
                        title=f'New chat from {_person(actor)}'[:220],
                        body=body[:160],
                        link=f'#workchat/{convo.pk}',
                    )
                    for recipient in recipients
                ])
            return JsonResponse({'ok':True, 'message':_message(message)})
        if action == 'read_chat':
            convo = _is_chat_member(actor, data.get('conversationId'))
            ChatParticipant.objects.filter(conversation=convo,member=actor).update(last_read_at=timezone.now())
            return JsonResponse({'ok':True})
        if action == 'add_chat_members':
            convo = _is_chat_member(actor, data.get('conversationId'))
            if convo.kind != 'group' or actor.role not in ('manager','admin') and convo.created_by_id != actor.pk:
                raise PermissionError('Only the group creator or managers can invite team members')
            raw = data.get('memberIds', [])
            if not isinstance(raw, list):
                raise ValueError('Select members')
            try:
                ids = {int(i) for i in raw}
            except (TypeError,ValueError):
                raise ValueError('Invalid member')
            if len(ids) > 20 or _people(actor).filter(pk__in=ids).count() != len(ids):
                raise PermissionError('Only active employees can be invited')
            if convo.participants.count() + len(ids) > 20:
                raise ValueError('Group limit is 20 members')
            ChatParticipant.objects.bulk_create([ChatParticipant(conversation=convo, member_id=i) for i in ids],ignore_conflicts=True)
            _log(actor, 'Added group members', convo, detail=f'{len(ids)} members invited')
            return JsonResponse({'ok':True})
        if action == 'leave_chat':
            convo = _is_chat_member(actor, data.get('conversationId'))
            if convo.kind != 'group':
                raise PermissionError('Direct messages cannot be left')
            ChatParticipant.objects.filter(conversation=convo,member=actor).delete()
            _log(actor, 'Left internal conversation', convo, detail='Left a team group')
            return JsonResponse({'ok':True})
        raise ValueError('Unsupported action')
    except PermissionError as exc:
        return JsonResponse({'error':str(exc)},status=403)
    except (ValueError,TypeError,OverflowError) as exc:
        return JsonResponse({'error':str(exc)},status=400)


@require_http_methods(['GET'])
def conversation_messages(request, conversation_id):
    try:
        actor = _request_member(request)
        _staff(actor)
        convo = _is_chat_member(actor, conversation_id)
    except PermissionError as exc:
        return JsonResponse({'error':str(exc)},status=403)
    rows = list(convo.messages.select_related('sender__user').order_by('-created_at','-id')[:80])
    ChatParticipant.objects.filter(conversation=convo,member=actor).update(last_read_at=timezone.now())
    return JsonResponse({'conversation':_summary(convo,actor),'messages':[_message(row) for row in reversed(rows)]})


@require_http_methods(['GET', 'POST'])
def own_profile(request):
    try:
        member = _request_member(request)
        if request.method == 'GET':
            return JsonResponse(_profile_json(member))
        if not (request.content_type or '').startswith('multipart/form-data'):
            return JsonResponse({'error':'Use multipart/form-data'},status=415)
        user = member.user
        first = request.POST.get('firstName',user.first_name).strip()
        last = request.POST.get('lastName',user.last_name).strip()
        phone = request.POST.get('phone',member.phone).strip()
        if len(first)>150 or len(last)>150 or len(phone)>40:
            raise ValueError('Profile field too long')
        photo = request.FILES.get('photo')
        if photo:
            if photo.size > 2*1024*1024:
                raise ValueError('Profile photo must be smaller than 2 MB')
            try:
                with Image.open(photo) as im:
                    im.verify()
                photo.seek(0)
                with Image.open(photo) as original:
                    image=ImageOps.exif_transpose(original)
                    if image.width > 8000 or image.height > 8000 or image.width*image.height > 20_000_000:
                        raise ValueError('Photo dimensions are too large')
                    image=ImageOps.fit(image.convert('RGB'),(384,384),method=Image.Resampling.LANCZOS)
                    output=io.BytesIO()
                    image.save(output,'WEBP',quality=82,method=5)
            except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
                raise ValueError('Upload a valid JPG, PNG, or WebP photo')
            old_name = member.profile_photo.name if member.profile_photo else ''
            member.profile_photo.save(f'{member.pk}-avatar.webp',ContentFile(output.getvalue()),save=False)
            member.save(update_fields=['profile_photo'])
            if old_name and old_name != member.profile_photo.name:
                member.profile_photo.storage.delete(old_name)
        user.first_name,user.last_name=first,last
        user.save(update_fields=['first_name','last_name'])
        member.phone=phone
        member.save(update_fields=['phone'])
        if member.role in STAFF:
            _log(member, 'Updated employee profile', member, detail='Profile information or photo changed')
        return JsonResponse({'ok':True,**_profile_json(member)})
    except PermissionError as exc:
        return JsonResponse({'error':str(exc)},status=403)
    except ValueError as exc:
        return JsonResponse({'error':str(exc)},status=400)


def _profile_json(m):
    return {'id':m.pk,'name':_person(m),'firstName':m.user.first_name,'lastName':m.user.last_name,
            'email':m.user.email,'phone':m.phone,'role':m.role,'jobTitle':m.job_title,
            'photo':_photo(m),'googleLinked':bool(m.google_sub)}


@require_http_methods(['GET'])
def avatar_file(request, member_id):
    try:
        actor=_request_member(request)
        target = Member.objects.select_related('user').filter(pk=member_id,is_active=True).first()
        if not target or not target.profile_photo:
            raise Http404
        if actor.pk != target.pk:
            if actor.role in STAFF and target.role in STAFF:
                pass
            elif actor.role == 'client' and target.role in STAFF and ClientAssignment.objects.filter(
                client_id=actor.client_account_id,employee=target,active=True
            ).exists():
                pass
            else:
                raise PermissionError('Photo is not accessible')
        # FileResponse provides a streamed file rather than leaking MEDIA_ROOT.
        try:
            image_file=target.profile_photo.open('rb')
        except (OSError, ValueError):
            raise Http404
        result=FileResponse(image_file,content_type='image/webp')
        result['Cache-Control']='private, no-store'
        result['X-Content-Type-Options']='nosniff'
        return result
    except PermissionError:
        return JsonResponse({'error':'Photo is not accessible'},status=403)
