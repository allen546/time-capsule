from sanic import Blueprint
from sanic.response import json
import uuid
from db import ContactDB, async_session

bp = Blueprint('contacts', url_prefix='/api/contacts')

@bp.get('/')
async def get_contacts(request):
    """获取用户的所有联系人"""
    user_uuid = request.args.get('user_uuid')
    if not user_uuid:
        return json({'error': '缺少用户UUID'}, status=400)
    
    async with async_session() as session:
        contacts = await ContactDB.get_contacts_by_user(session, user_uuid)
        return json({
            'contacts': [{
                'id': contact.uuid,
                'name': contact.name,
                'relation': contact.relation,
                'phone': contact.phone,
                'address': contact.address,
                'notes': contact.notes,
                'created_at': contact.created_at.isoformat(),
                'updated_at': contact.updated_at.isoformat()
            } for contact in contacts]
        })

@bp.get('/<contact_uuid>')
async def get_contact(request, contact_uuid):
    """获取单个联系人"""
    async with async_session() as session:
        contact = await ContactDB.get_contact(session, contact_uuid)
        if not contact:
            return json({'error': '联系人不存在'}, status=404)
        
        return json({
            'contact': {
                'id': contact.uuid,
                'name': contact.name,
                'relation': contact.relation,
                'phone': contact.phone,
                'address': contact.address,
                'notes': contact.notes,
                'created_at': contact.created_at.isoformat(),
                'updated_at': contact.updated_at.isoformat()
            }
        })

@bp.post('/')
async def create_contact(request):
    """创建新联系人"""
    data = request.json
    required_fields = ['user_uuid', 'name', 'relation', 'phone']
    
    for field in required_fields:
        if field not in data:
            return json({'error': f'缺少必填字段: {field}'}, status=400)
    
    contact_uuid = str(uuid.uuid4())
    
    async with async_session() as session:
        contact = await ContactDB.create_contact(
            session,
            contact_uuid,
            data['user_uuid'],
            data['name'],
            data['relation'],
            data['phone'],
            data.get('address'),
            data.get('notes')
        )
        
        return json({
            'contact': {
                'id': contact.uuid,
                'name': contact.name,
                'relation': contact.relation,
                'phone': contact.phone,
                'address': contact.address,
                'notes': contact.notes,
                'created_at': contact.created_at.isoformat(),
                'updated_at': contact.updated_at.isoformat()
            }
        }, status=201)

@bp.put('/<contact_uuid>')
async def update_contact(request, contact_uuid):
    """更新联系人信息"""
    data = request.json
    required_fields = ['name', 'relation', 'phone']
    
    for field in required_fields:
        if field not in data:
            return json({'error': f'缺少必填字段: {field}'}, status=400)
    
    async with async_session() as session:
        contact = await ContactDB.update_contact(
            session,
            contact_uuid,
            data['name'],
            data['relation'],
            data['phone'],
            data.get('address'),
            data.get('notes')
        )
        
        if not contact:
            return json({'error': '联系人不存在'}, status=404)
        
        return json({
            'contact': {
                'id': contact.uuid,
                'name': contact.name,
                'relation': contact.relation,
                'phone': contact.phone,
                'address': contact.address,
                'notes': contact.notes,
                'created_at': contact.created_at.isoformat(),
                'updated_at': contact.updated_at.isoformat()
            }
        })

@bp.delete('/<contact_uuid>')
async def delete_contact(request, contact_uuid):
    """删除联系人"""
    async with async_session() as session:
        success = await ContactDB.delete_contact(session, contact_uuid)
        if not success:
            return json({'error': '联系人不存在'}, status=404)
        
        return json({'message': '联系人已删除'}) 