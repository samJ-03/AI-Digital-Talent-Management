"""T18纯规则测试：有原文来源的合成事实，不访问模型、网络或数据库。"""
from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.ingestion.extraction_types import ResumeFacts,EmploymentFact
from app.jobs.schemas import Condition

AS_OF=date(2026,11,10)


def facts(education=None,employment=None,skills=None,certificates=None,birth_date=None,quotes=None):
    """逐叶生成证据，仍执行正式ResumeFacts验证，不跳过来源契约。"""
    data={'identity':{'name':'合成人才','birth_date':birth_date},'contacts':{'email':None,'phone':None},'education':education or [],'employment':employment or [],'projects':[],'skills':skills or [],'certificates':certificates or []}
    sources={};citations=[]
    def walk(value,path):
        if isinstance(value,dict):
            for k,v in value.items():walk(v,path+'.'+k if path else k)
        elif isinstance(value,list):
            for i,v in enumerate(value):walk(v,path+'.'+str(i))
        elif value is not None:
            evidence={'source_type':'stored_file','source_id':'synthetic1','locator':path,'quote':(quotes or {}).get(path,value)}
            sources[path]=[evidence];citations.append(evidence)
    walk(data,'');return ResumeFacts.model_validate({**data,'field_sources':sources,'citations':citations})


def degree(value='本科',major='软件工程',end='2020-06-30'):
    return {'school':'合成大学','degree':value,'major':major,'start_date':'2016-09-01','end_date':end}


def rule(field,expected,operator=None,required=True,key=None):
    operators={'education':'gte','major':'eq','relevant_years':'gte','skill':'contains_all','certificate':'contains_all'}
    return Condition(key=key or field,field=field,operator=operator or operators[field],expected=expected,required=required)


@pytest.mark.parametrize('major,expected',[('软件工程','pass'),('会计学','fail'),('计算机相关','unknown')])
def test_required_truth_table(major,expected):
    from app.evaluation.rules import ScreeningEngine
    report=ScreeningEngine(as_of=AS_OF).evaluate(facts(education=[degree(major=major)]),[rule('education','bachelor'),rule('major','软件工程')])
    assert report.result==expected
    assert len(report.details)==2 and all(d.evidence for d in report.details)


def test_preferred_missing_not_fail():
    from app.evaluation.rules import ScreeningEngine
    report=ScreeningEngine(as_of=AS_OF).evaluate(facts(education=[degree()]),[rule('education','bachelor'),rule('certificate',['PMP'],required=False)])
    assert report.result=='pass' and report.details[1].result=='unknown'


def test_overlapping_employment_no_double_count():
    from app.evaluation.normalization import ExperienceCalculator
    employment=[EmploymentFact(company='A',start_date='2018-01-01',end_date='2020-01-01'),EmploymentFact(company='B',start_date='2019-01-01',end_date='2022-01-01')]
    assert ExperienceCalculator().relevant_years(employment,AS_OF)==Decimal('4')


def test_age_manual_only():
    with pytest.raises(ValidationError):Condition(key='age',field='age',operator='lte',expected=35,required=True)
    from app.evaluation.rules import ScreeningEngine
    engine=ScreeningEngine(as_of=AS_OF)
    conditions=[rule('skill',['Python'])]
    assert engine.evaluate(facts(skills=['Python'],birth_date='1960-01-01'),conditions).result==engine.evaluate(facts(skills=['Python'],birth_date='2000-01-01'),conditions).result=='pass'


def test_unknown_major_requires_review():
    from app.evaluation.normalization import MajorNormalizer
    result=MajorNormalizer().resolve('CS','core-major-v1')
    assert result.canonical is None and result.needs_review and result.confidence<1


@pytest.mark.parametrize('value,code',[('本科','bachelor'),('硕士研究生','master'),('大专','associate'),('博士','doctor'),('High School','high_school'),('中专','secondary'),('Bachelor of Science','bachelor')])
def test_education_aliases(value,code):
    from app.evaluation.normalization import EducationNormalizer
    assert EducationNormalizer().normalize(value).code==code


@pytest.mark.parametrize('value',[None,'本科在读','本科/硕士','未取得本科学历','自述高学历'])
def test_ambiguous_degree_unknown(value):
    from app.evaluation.normalization import EducationNormalizer
    assert EducationNormalizer().normalize(value) is None


def test_future_degree_does_not_count_as_earned():
    from app.evaluation.rules import ScreeningEngine
    report=ScreeningEngine(as_of=AS_OF).evaluate(facts(education=[degree('硕士',end='2027-06-30')]),[rule('education','master')])
    assert report.result=='unknown'


def test_missing_graduation_not_assumed_earned():
    from app.evaluation.rules import ScreeningEngine
    assert ScreeningEngine(as_of=AS_OF).evaluate(facts(education=[degree(end=None)]),[rule('education','bachelor')]).result=='unknown'


def test_major_cannot_borrow_lower_degree():
    from app.evaluation.rules import ScreeningEngine
    resume=facts(education=[degree('大专','软件工程'),degree('本科','会计学')])
    assert ScreeningEngine(as_of=AS_OF).evaluate(resume,[rule('education','bachelor'),rule('major','软件工程')]).result=='fail'


def test_explicit_alias_major_matches():
    from app.evaluation.rules import ScreeningEngine
    assert ScreeningEngine(as_of=AS_OF).evaluate(facts(education=[degree(major='Software Engineering')]),[rule('major','软件工程')]).result=='pass'


def test_unknown_dictionary_fails_closed():
    from app.evaluation.normalization import MajorNormalizer
    with pytest.raises(ValueError):MajorNormalizer().resolve('软件工程','missing-revision')


@pytest.mark.parametrize('employment',[[],[EmploymentFact(company='A')],[EmploymentFact(company='A',start_date='2020-01-01',end_date='2019-01-01')]])
def test_missing_or_conflicting_dates_not_zero(employment):
    from app.evaluation.normalization import ExperienceCalculator
    assert ExperienceCalculator().relevant_years(employment,AS_OF) is None


def test_partial_month_precision_crossing_threshold_unknown():
    from app.evaluation.rules import ScreeningEngine
    resume=facts(employment=[{'company':'A','start_date':'2020-01','end_date':'2021-01'}])
    result=ScreeningEngine(as_of=AS_OF,relevant_employment_indices=(0,)).evaluate(resume,[rule('relevant_years',1)])
    assert result.result=='unknown'


def test_total_experience_not_automatically_relevant():
    from app.evaluation.rules import ScreeningEngine
    resume=facts(employment=[{'company':'A','start_date':'2010-01-01','end_date':'2020-01-01'}])
    assert ScreeningEngine(as_of=AS_OF).evaluate(resume,[rule('relevant_years',3)]).result=='unknown'


def test_confirmed_relevant_experience_exact_threshold():
    from app.evaluation.rules import ScreeningEngine
    resume=facts(employment=[{'company':'A','start_date':'2018-01-01','end_date':'2022-01-01'}])
    report=ScreeningEngine(as_of=AS_OF,relevant_employment_indices=(0,)).evaluate(resume,[rule('relevant_years',4)])
    assert report.result=='pass' and report.details[0].evidence


def test_skill_full_token_no_cpp_substring():
    from app.evaluation.rules import ScreeningEngine
    report=ScreeningEngine(as_of=AS_OF).evaluate(facts(skills=['C++']),[rule('skill',['C'])])
    assert report.result=='unknown'


def test_negative_evidence_never_counts_as_met():
    from app.evaluation.rules import ScreeningEngine
    report=ScreeningEngine(as_of=AS_OF).evaluate(facts(skills=['Python'],quotes={'skills.0':'不熟悉Python'}),[rule('skill',['Python'])])
    assert report.result=='unknown'


def test_certificate_casefold_exact_and_no_mutation():
    from app.evaluation.rules import ScreeningEngine
    resume=facts(certificates=['PMP']);before=resume.model_dump()
    report=ScreeningEngine(as_of=AS_OF).evaluate(resume,[rule('certificate',['pmp'])])
    assert report.result=='pass' and resume.model_dump()==before and report.as_of==AS_OF


def test_duplicate_condition_keys_rejected():
    from app.evaluation.rules import ScreeningEngine
    with pytest.raises(ValueError):ScreeningEngine(as_of=AS_OF).evaluate(facts(skills=['Python']),[rule('skill',['Python']),rule('skill',['SQL'])])


def test_distinct_mechanical_majors_are_not_aliases():
    from app.evaluation.normalization import MajorNormalizer
    normalizer=MajorNormalizer()
    assert normalizer.resolve('机械工程','core-major-v1').canonical!=normalizer.resolve('机械设计制造及其自动化','core-major-v1').canonical


def test_english_negative_evidence_not_positive():
    from app.evaluation.rules import ScreeningEngine
    report=ScreeningEngine(as_of=AS_OF).evaluate(facts(skills=['Python'],quotes={'skills.0':'no Python experience'}),[rule('skill',['Python'])])
    assert report.result=='unknown'


def test_unrelated_negative_fact_does_not_hide_positive():
    from app.evaluation.rules import ScreeningEngine
    resume=facts(skills=['Python','Java'],quotes={'skills.1':'不熟悉Java'})
    result=ScreeningEngine(as_of=AS_OF).evaluate(resume,[rule('skill',['Python']),rule('skill',['Java'],required=False,key='preferred_java')])
    assert result.result=='pass' and result.details[0].result=='met' and result.details[1].result=='unknown'


def test_required_failure_takes_precedence_over_unknown():
    from app.evaluation.rules import ScreeningEngine
    result=ScreeningEngine(as_of=AS_OF).evaluate(facts(education=[degree('高中',major=None)]),[rule('education','bachelor'),rule('major','软件工程')])
    assert result.result=='fail' and {d.result for d in result.details}=={'unknown','unmet'}


@pytest.mark.parametrize('operator,expected,result',[('lte',3,'fail'),('lte',4,'pass'),('between',[3,5],'pass'),('between',[5,7],'fail')])
def test_experience_bound_operators(operator,expected,result):
    from app.evaluation.rules import ScreeningEngine
    resume=facts(employment=[{'company':'A','start_date':'2018-01-01','end_date':'2022-01-01'}])
    report=ScreeningEngine(as_of=AS_OF,relevant_employment_indices=(0,)).evaluate(resume,[rule('relevant_years',expected,operator)])
    assert report.result==result


def test_future_work_dates_unknown():
    from app.evaluation.normalization import ExperienceCalculator
    assert ExperienceCalculator().relevant_years([EmploymentFact(company='A',start_date='2025-01-01',end_date='2027-01-01')],AS_OF) is None


def test_ongoing_work_uses_frozen_date():
    from app.evaluation.normalization import ExperienceCalculator
    calculator=ExperienceCalculator();work=[EmploymentFact(company='A',start_date='2020-01-01',end_date='至今')]
    assert calculator.relevant_years(work,date(2024,1,1))==4
    assert calculator.relevant_years(work,date(2025,1,1))==5


def test_unsupported_operator_and_sensitive_fields_rejected():
    for field in ['age','gender','marital_status','health','loyalty']:
        with pytest.raises(ValidationError):Condition(key='sensitive',field=field,operator='eq',expected='x',required=True)
    with pytest.raises(ValidationError):rule('education','bachelor','contains_any')


def test_rules_run_with_network_disabled(monkeypatch):
    import socket
    def deny(*args,**kwargs):raise AssertionError('Pure screening must not open a network connection')
    monkeypatch.setattr(socket,'create_connection',deny)
    from app.evaluation.rules import ScreeningEngine
    assert ScreeningEngine(as_of=AS_OF).evaluate(facts(skills=['PYTHON']),[rule('skill',['Python'])]).result=='pass'


def test_ambiguous_date_precision_not_scalar_zero():
    from app.evaluation.normalization import ExperienceCalculator
    employment=[EmploymentFact(company='A',start_date='2020-01',end_date='2020-01')]
    assert ExperienceCalculator().relevant_years(employment,AS_OF) is None


@pytest.mark.parametrize('field',['major','education','relevant_years'])
def test_review_uncertain_evidence_cannot_hard_reject(field):
    from app.evaluation.rules import ScreeningEngine
    if field=='major':
        resume=facts(education=[degree(major='会计学')],quotes={'education.0.major':'待核实：会计学'});condition=rule('major','软件工程');indices=None
    elif field=='education':
        resume=facts(education=[degree('高中')],quotes={'education.0.degree':'可能是高中'});condition=rule('education','bachelor');indices=None
    else:
        resume=facts(employment=[{'company':'A','start_date':'2018-01-01','end_date':'2022-01-01'}],quotes={'employment.0.end_date':'待核实：2022-01-01'});condition=rule('relevant_years',5);indices=(0,)
    assert ScreeningEngine(as_of=AS_OF,relevant_employment_indices=indices).evaluate(resume,[condition]).result=='unknown'


def test_review_confirmed_degree_ignores_uncertain_major():
    from app.evaluation.rules import ScreeningEngine
    resume=facts(education=[degree(major='会计学')],quotes={'education.0.major':'待核实：会计学'})
    result=ScreeningEngine(as_of=AS_OF).evaluate(resume,[rule('education','bachelor')])
    assert result.result=='pass'
    assert all(not e.locator.endswith('.major') for e in result.details[0].evidence)


def test_review_selected_experience_ignores_other_record():
    from app.evaluation.rules import ScreeningEngine
    resume=facts(employment=[{'company':'A','start_date':'2018-01-01','end_date':'2022-01-01'},{'company':'B','responsibilities':'不熟悉Java'}])
    result=ScreeningEngine(as_of=AS_OF,relevant_employment_indices=(0,)).evaluate(resume,[rule('relevant_years',4)])
    assert result.result=='pass' and all(e.locator.startswith('employment.0.') for e in result.details[0].evidence)


def test_review_years_ignore_responsibilities_of_same_record():
    from app.evaluation.rules import ScreeningEngine
    resume=facts(employment=[{'company':'A','start_date':'2018-01-01','end_date':'2022-01-01','responsibilities':'不熟悉Java'}])
    result=ScreeningEngine(as_of=AS_OF,relevant_employment_indices=(0,)).evaluate(resume,[rule('relevant_years',4)])
    assert result.result=='pass'
    assert all(e.locator.endswith(('.start_date','.end_date')) for e in result.details[0].evidence)


@pytest.mark.parametrize('status',['在读','肄业','结业','in progress'])
def test_review_degree_status_in_source_not_lost(status):
    from app.evaluation.rules import ScreeningEngine
    resume=facts(education=[degree()],quotes={'education.0.degree':f'本科 {status}'})
    assert ScreeningEngine(as_of=AS_OF).evaluate(resume,[rule('education','bachelor')]).result=='unknown'
