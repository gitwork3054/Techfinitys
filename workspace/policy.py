ROLES = ['client','employee','manager','admin']

# Feature permissions are deliberately separate from hierarchy/data visibility,
# mirroring mature CRM systems: hierarchy says WHICH records are visible,
# permissions say WHAT actions are available.
DEFAULT_PERMISSIONS = {
    'client': {'clients:read','projects:read','tasks:read','updates:read','updates:write','notes:read','notes:write','calendar:read','files:read','tickets:read','tickets:write','content:read','content:write','invoices:read','issues:read','collaboration:read','collaboration:write'},
    'employee': {'clients:read','projects:read','tasks:read','tasks:write','updates:read','updates:write','notes:read','notes:write','calendar:read','calendar:write','files:read','files:write','tickets:read','tickets:write','content:read','content:write','deliverables:read','deliverables:write','packages:read','campaigns:read','shoots:read','shoots:write','invoices:read','workflows:read','issues:read','issues:write','phases:read','phases:write','timelogs:read','timelogs:write','timesheets:read','timesheets:write','collaboration:read','collaboration:write','approvals:read','approvals:write'},
    'manager': {'*'},
    'admin': {'*'},
}

LEGACY_CLIENT_KINDS = ['packages','deliverables','invoices','tickets','content','campaigns','shoots','files','notifications','mandates','issues','phases','timelogs','timesheets','collaboration','approvals']
LEGACY_TEAM_KINDS = LEGACY_CLIENT_KINDS + ['workflows','settings','integrations','audit','reports']
ALL_KINDS = LEGACY_TEAM_KINDS + ['clients','employees','tasks','projects','updates','notes','calendar','assignments']

def has_permission(role, permission, grants=None):
    grants = set(grants or [])
    base = DEFAULT_PERMISSIONS.get(role, set())
    return '*' in base or permission in base or permission in grants

def allowed(role, kind, action, grants=None):
    if role in ('admin','manager'):
        return True
    if kind in ('clients','employees','assignments'):
        return action == 'read' and role in ('employee','client')
    return has_permission(role, f'{kind}:{action}', grants)

def visible_legacy(role, client_codes, row):
    if role in ('admin','manager'):
        return True
    return row.get('client') in set(client_codes or []) or (role == 'employee' and row.get('client') == 'org')
