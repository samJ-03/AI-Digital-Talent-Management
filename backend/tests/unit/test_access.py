from datetime import datetime, timezone
import pytest
from app.core.access import AccessPolicy, ActorContext, ResourceScope, PermissionDenied
from app.core.clock import Clock, FrozenClock

def test_admin_not_hr():
    with pytest.raises(PermissionDenied):
        AccessPolicy().require(ActorContext('admin',user_id=1,permissions=frozenset({'user.manage'})), 'talent.read', ResourceScope('talent',id=2,shared=True))

def test_shared_talent_requires_permission():
    p=AccessPolicy()
    hr=ActorContext('hr',user_id=1,department_ids=frozenset({10}),permissions=frozenset({'talent.read'}))
    p.require(hr,'talent.read',ResourceScope('talent',id=2,shared=True))
    with pytest.raises(PermissionDenied): p.require(hr,'talent.write',ResourceScope('talent',id=2,shared=True))

def test_private_cross_department_denied_even_marked_shared():
    p=AccessPolicy()
    hr=ActorContext('hr',user_id=1,department_ids=frozenset({10}),permissions=frozenset({'exam.read'}))
    p.require(hr,'exam.read',ResourceScope('exam',id=2,department_id=10))
    with pytest.raises(PermissionDenied): p.require(hr,'exam.read',ResourceScope('exam',id=2,department_id=20,shared=True))

def test_company_scope_is_permission_specific():
    actor=ActorContext('hr',user_id=1,permissions=frozenset({'exam.read','talent.read'}),company_permissions=frozenset({'talent.read'}))
    with pytest.raises(PermissionDenied): AccessPolicy().require(actor,'exam.read',ResourceScope('exam',id=2,department_id=20))

def test_explicit_company_scope_allows_own_permission():
    actor=ActorContext('hr',user_id=1,permissions=frozenset({'exam.read'}),company_permissions=frozenset({'exam.read'}))
    AccessPolicy().require(actor,'exam.read',ResourceScope('exam',id=2,department_id=20))

def test_candidate_cannot_reuse_staff_or_other_attempt_context():
    actor=ActorContext('candidate',candidate_id=5,attempt_id=7,permissions=frozenset({'exam.answer','talent.read'}))
    p=AccessPolicy()
    p.require(actor,'exam.answer',ResourceScope('exam_attempt',id=7))
    for permission,scope in [('talent.read',ResourceScope('talent',id=5,shared=True)),('exam.answer',ResourceScope('exam_attempt',id=8)),('exam.answer',ResourceScope('exam_attempt',id=7,department_id=1))]:
        with pytest.raises(PermissionDenied): p.require(actor,permission,scope)

def test_hr_cannot_manage_accounts():
    with pytest.raises(PermissionDenied): AccessPolicy().require(ActorContext('hr',user_id=1,permissions=frozenset({'user.manage'})),'user.manage',ResourceScope('user',id=2))

def test_clock_is_utc_and_frozen_clock_rejects_naive():
    assert Clock().now().utcoffset().total_seconds()==0
    instant=datetime(2026,11,5,2,0,tzinfo=timezone.utc)
    assert FrozenClock(instant).now()==instant
    with pytest.raises(ValueError): FrozenClock(datetime(2026,11,5))


def test_company_knowledge_is_shared_without_private_department_bypass():
    actor=ActorContext('hr',user_id=1,department_ids=frozenset({10}),permissions=frozenset({'knowledge.read'}))
    AccessPolicy().require(actor,'knowledge.read',ResourceScope('knowledge',id=2,shared=True))
    with pytest.raises(PermissionDenied): AccessPolicy().require(actor,'knowledge.read',ResourceScope('knowledge',id=2,department_id=20,shared=True))
