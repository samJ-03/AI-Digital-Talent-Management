"""Two local synthetic, department-isolated published papers; no AI or email calls."""
import json
from sqlalchemy import select
from app.core.errors import DomainError
from app.core.settings import Settings
from app.core.uow import make_uow
from app.identity.models import User
from app.identity.views import resolve_user
from app.assessment.question_service import QuestionService
from app.assessment.paper_service import PaperService
from app.assessment.schemas import QuestionBankCreate,QuestionDraft,PaperCreate,PaperVersionDraft

SAMPLES=[
    {'tag':'analysis','login':'hr-tech','name':'数据分析岗位演示卷A','bank':'演示题库-数据分析',
     'single':('数列1、2、3的算术平均值是多少？',[('A','1'),('B','2'),('C','3')],['B']),
     'multiple':('处理缺失值前应先核实哪些信息？',[('A','缺失比例'),('B','字段业务含义'),('C','直接把所有缺失改为0'),('D','数据来源')],['A','B','D']),
     'short':('面对一份销售数据，如何检查缺失值并选择处理方法？','统计缺失比例、核实业务含义和原因；结合字段选择补充数据、保留缺失或合理插补，并记录验证结果。')},
    {'tag':'operations','login':'hr-ops','name':'运营岗位演示卷B','bank':'演示题库-运营',
     'single':('活动有100次访问和10次成交，按成交次数除以访问次数计算的转化率是多少？',[('A','1%'),('B','10%'),('C','90%')],['B']),
     'multiple':('以下哪些信息适合用于活动复盘？',[('A','目标达成情况'),('B','成本投入'),('C','数据口径'),('D','只保留正面结果')],['A','B','C']),
     'short':('请给出一次活动复盘的基本步骤。','明确目标和统计口径，核对数据，分析达成情况与偏差，提出改进并安排后续验证。')},
]

def actor_for(login):
    with make_uow() as uow:
        user=uow.session.scalar(select(User).where(User.login_name==login))
        if user is None or user.department_id is None: raise RuntimeError('Local HR bootstrap required')
        return resolve_user(uow.session,user),user.department_id

def main():
    if Settings.load().environment!='dev': raise RuntimeError('Synthetic local samples only')
    papers=[];actors=[]
    for sample in SAMPLES:
        actor,department=actor_for(sample['login']);actors.append(actor)
        prefix='local-sample:'+sample['tag']+':v1:'
        bank=QuestionService(make_uow,prefix+'bank').create_bank(actor,QuestionBankCreate(name=sample['bank'],department_id=department))
        question_ids=[]
        for index,kind in enumerate(('single_choice','multiple_choice','short_answer')):
            key=prefix+'question:'+str(index)
            if kind=='short_answer':
                stem,reference=sample['short']
                draft=QuestionDraft(bank_id=int(bank.id),type=kind,stem=stem,rubric={'reference_answer':reference,'criteria':[
                    {'key':'facts','description':'识别信息与核对事实','weight':2},
                    {'key':'method','description':'提出合理方法并说明原因','weight':3},
                    {'key':'validation','description':'记录结果并安排验证','weight':1}]})
            else:
                stem,options,selected=sample['single' if kind=='single_choice' else 'multiple']
                draft=QuestionDraft(bank_id=int(bank.id),type=kind,stem=stem,options=[{'key':k,'text':text} for k,text in options],answer_key={'selected_keys':selected})
            question=QuestionService(make_uow,key).create(actor,draft)
            QuestionService(make_uow,key+':approve').approve(actor,int(question.id),'本地合成演示题，经人工校验标准')
            question_ids.append(int(question.id))
        paper=PaperService(make_uow,prefix+'paper').create(actor,PaperCreate(name=sample['name'],department_id=department))
        draft=PaperVersionDraft(duration_minutes=45,reference_pass_score='60.00',items=[{'source_question_id':qid,'max_score':score,'position_no':i+1} for i,(qid,score) in enumerate(zip(question_ids,('20.00','40.00','40.00')))])
        version=PaperService(make_uow,prefix+'draft').draft_version(actor,int(paper.id),draft)
        published=PaperService(make_uow,prefix+'publish').publish(actor,int(version.id),'本地合成岗位样例验收')
        papers.append({'tag':sample['tag'],'paper_id':paper.id,'paper_version_id':published.id,'department_id':str(department),'question_count':len(published.items),'total_score':format(published.total_score,'.2f'),'state':published.status})
    isolated=False
    try: PaperService().get_version(actors[0],int(papers[1]['paper_version_id']))
    except DomainError as error: isolated=error.http_status==404
    print(json.dumps({'ready':isolated and len(papers)==2,'papers':papers,'cross_department_denied':isolated,'synthetic_only':True,'ai_or_email_called':False},ensure_ascii=False))
    return 0 if isolated else 1

if __name__=='__main__': raise SystemExit(main())
