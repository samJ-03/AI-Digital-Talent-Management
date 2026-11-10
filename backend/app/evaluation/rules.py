"""确定性三态硬筛：无模型、数据库、网络、隐式当前日期或业务副作用。"""
from datetime import date
from decimal import Decimal
import re
from app.ingestion.extraction_types import ResumeFacts
from app.evaluation.schemas import ScreeningCondition,ScreeningDetail,ScreeningReport
from app.evaluation.normalization import EducationNormalizer,MajorNormalizer,ExperienceCalculator,date_bounds,ongoing,token,NORMALIZATION_REVISION,MAJOR_REVISION


def qualified(quote):
    """引文含否定/未定状态时不把截取关键词当正向证据，交人工核实。"""
    text=token(quote)
    return any(v in text for v in ['不熟悉','不会','不具备','未取得','未获得','未毕业','未掌握','不掌握','不了解','尚未','待核实','待确认','可能','没有','没用过','未使用','未接触']) or bool(re.search(r'\b(no|not|never|without|lack|unfamiliar|learning)\b',text))


class ScreeningEngine:
    """评估日期必须由T19快照提供；相关经历索引必须来自已确认的岗位上下文。"""
    def __init__(self,*,as_of: date,dictionary_revision=MAJOR_REVISION,relevant_employment_indices=None):
        if type(as_of) is not date:raise ValueError('A frozen date is required')
        MajorNormalizer().resolve(None,dictionary_revision)
        self.as_of=as_of;self.dictionary_revision=dictionary_revision
        self.relevant_indices=relevant_employment_indices
        if relevant_employment_indices is not None and (not isinstance(relevant_employment_indices,tuple) or not relevant_employment_indices or any(type(i) is not int or i<0 for i in relevant_employment_indices) or len(set(relevant_employment_indices))!=len(relevant_employment_indices)):raise ValueError('Invalid confirmed relevance indices')

    def evaluate(self,facts: ResumeFacts,conditions: list[ScreeningCondition]) -> ScreeningReport:
        """先重新验证输入，逐条件留存证据，仅required参与总三态。"""
        data=ResumeFacts.model_validate(facts.model_dump(exclude={'ai_run_id'}))
        rules=[ScreeningCondition.model_validate(c.model_dump() if hasattr(c,'model_dump') else c) for c in conditions]
        if len(rules)>50 or len({c.key for c in rules})!=len(rules):raise ValueError('Invalid or duplicate conditions')
        if self.relevant_indices and max(self.relevant_indices)>=len(data.employment):raise ValueError('Relevance index outside resume')
        observations=[self._education_observation(e,i,data) for i,e in enumerate(data.education)]
        details=[]
        for condition in rules:
            if condition.field=='education':result,actual,reason,paths=self._education(condition,observations)
            elif condition.field=='major':result,actual,reason,paths=self._major(condition,observations,rules,data)
            elif condition.field=='relevant_years':result,actual,reason,paths=self._experience(condition,data)
            else:result,actual,reason,paths=self._tokens(condition,data)
            evidence=self._evidence(data,paths)
            details.append(ScreeningDetail(condition_key=condition.key,required=condition.required,expected=condition.expected,actual=actual,result=result,evidence=evidence,reason_code=reason))
        required=[d.result for d in details if d.required]
        overall='fail' if 'unmet' in required else 'unknown' if 'unknown' in required else 'pass'
        return ScreeningReport(result=overall,details=details,as_of=self.as_of,dictionary_revision=self.dictionary_revision,normalization_revision=NORMALIZATION_REVISION)

    @staticmethod
    def _evidence(facts,paths):
        result=[]
        for path in paths:
            for source in facts.field_sources.get(path,[]):
                if source not in result:result.append(source)
        return result

    @staticmethod
    def _uncertain(facts,paths):
        return any(qualified(e.quote) for e in ScreeningEngine._evidence(facts,paths))

    @staticmethod
    def _degree_paths(observations):
        return [f"education.{o['index']}.{field}" for o in observations for field in ['degree','start_date','end_date']]

    def _education_observation(self,entry,index,facts):
        level=EducationNormalizer().normalize(entry.degree);raw=token(entry.degree)
        end=date_bounds(entry.end_date);start=date_bounds(entry.start_date)
        if ongoing(entry.end_date) or any(v in raw for v in ['在读','未毕业','未取得','肄业']):completed=False
        elif end is not None:
            completed=None if start and start[0]>end[1] else True if end[1]<=self.as_of else False if end[0]>self.as_of else None
        elif entry.end_date is not None:completed=None
        else:completed=True if any(v in raw for v in ['毕业','已取得']) else None
        # Evidence certainty belongs to the field being compared. A doubtful
        # major does not invalidate a separately confirmed earned degree.
        if self._uncertain(facts,[f'education.{index}.degree']):level=None
        degree_quotes=[token(e.quote) for e in self._evidence(facts,[f'education.{index}.degree'])]
        if any(any(status in quote for status in ['在读','肄业','结业','未毕业','未取得','in progress']) for quote in degree_quotes):
            level=None
            if completed is not False:completed=None
        if self._uncertain(facts,[f'education.{index}.start_date',f'education.{index}.end_date']):completed=None
        return {'index':index,'level':level,'completed':completed,'major':entry.major}

    def _education(self,condition,observations):
        known=[o['level'] for o in observations if o['completed'] is True and o['level'] is not None]
        uncertain=[o for o in observations if o['completed'] is None or o['completed'] is True and o['level'] is None]
        paths=self._degree_paths(observations)
        actual={'highest':[],'uncertain_records':len(uncertain)}
        if not known:return 'unknown',actual,'NO_CONFIRMED_EARNED_DEGREE',paths
        rank=max(v.rank for v in known);highest={v.code for v in known if v.rank==rank};actual['highest']=sorted(highest)
        if condition.operator=='gte':
            expected=EducationNormalizer().normalize(condition.expected)
            if rank>=expected.rank:
                supporting=[o for o in observations if o['completed'] is True and o['level'] is not None and o['level'].rank>=expected.rank]
                actual['supporting_records']=[o['index'] for o in supporting]
                return 'met',actual,'EARNED_DEGREE_MET',self._degree_paths(supporting)
            return ('unknown' if uncertain else 'unmet'),actual,'DEGREE_UNCERTAIN' if uncertain else 'EARNED_DEGREE_BELOW_REQUIRED',paths
        if uncertain:return 'unknown',actual,'HIGHEST_DEGREE_UNCERTAIN',paths
        allowed={condition.expected} if condition.operator=='eq' else set(condition.expected)
        if highest<=allowed:return 'met',actual,'EARNED_DEGREE_MET',paths
        if highest & allowed:return 'unknown',actual,'PARALLEL_DEGREE_TYPES',paths
        return 'unmet',actual,'EARNED_DEGREE_NOT_ALLOWED',paths

    @staticmethod
    def _eligible_level(level,condition):
        if level is None:return None
        if condition.operator=='gte':return level.rank>=EducationNormalizer().normalize(condition.expected).rank
        return level.code==condition.expected if condition.operator=='eq' else level.code in condition.expected

    def _major(self,condition,observations,rules,facts):
        expected=[condition.expected] if condition.operator=='eq' else condition.expected
        resolved=[MajorNormalizer().resolve(v,self.dictionary_revision) for v in expected]
        if any(v.needs_review for v in resolved):return 'unknown',None,'UNRECOGNIZED_MAJOR_REQUIREMENT',[]
        wanted={v.canonical for v in resolved};known=[];uncertain=False;considered=[];supporting=[]
        required_degrees=[c for c in rules if c.field=='education' and c.required]
        for o in observations:
            if o['completed'] is False:continue
            eligible=[self._eligible_level(o['level'],r) for r in required_degrees]
            if False in eligible:continue
            considered.append(o)
            if o['completed'] is not True or None in eligible:uncertain=True;continue
            if self._uncertain(facts,[f"education.{o['index']}.major"]):uncertain=True;continue
            result=MajorNormalizer().resolve(o['major'],self.dictionary_revision)
            if result.needs_review:uncertain=True
            else:
                known.append(result.canonical)
                if result.canonical in wanted:supporting.append(o)
        def sources(records):
            fields=['major','start_date','end_date']+(['degree'] if required_degrees else [])
            return [f"education.{o['index']}.{field}" for o in records for field in fields]
        actual={'canonical':sorted(set(known)),'needs_review':uncertain,'dictionary_revision':self.dictionary_revision}
        if supporting:return 'met',actual,'CONFIRMED_MAJOR_MET',sources(supporting)
        if not known or uncertain:return 'unknown',actual,'MAJOR_REQUIRES_REVIEW',sources(considered)
        return 'unmet',actual,'CONFIRMED_MAJOR_NOT_ALLOWED',sources(considered)

    def _experience(self,condition,facts):
        indices=self.relevant_indices
        selected=range(len(facts.employment)) if indices is None else indices
        paths=[f'employment.{i}.{field}' for i in selected for field in ['start_date','end_date']]
        if self._uncertain(facts,paths):return 'unknown',None,'DATE_EVIDENCE_UNCERTAIN',paths
        records=facts.employment if indices is None else [facts.employment[i] for i in indices]
        bounds=ExperienceCalculator().bounds(records,self.as_of)
        if bounds is None:return 'unknown',None,'MISSING_OR_CONFLICTING_DATES',paths
        low=bounds.min_years if indices is not None else Decimal(0);high=bounds.max_years
        actual={'min_years':str(low),'max_years':str(high),'relevance_confirmed':indices is not None,'selected_indices':list(indices) if indices is not None else None}
        if indices is None:return 'unknown',actual,'RELEVANCE_NOT_CONFIRMED',paths
        value=condition.expected
        if condition.operator=='gte':
            target=Decimal(str(value));result='met' if low>=target else 'unmet' if high<target else 'unknown'
        elif condition.operator=='lte':
            target=Decimal(str(value));result='met' if high<=target else 'unmet' if low>target else 'unknown'
        else:
            left,right=[Decimal(str(v)) for v in value];result='met' if left<=low and high<=right else 'unmet' if high<left or low>right else 'unknown'
        return result,actual,'EXPERIENCE_'+result.upper(),paths

    def _tokens(self,condition,facts):
        values=facts.skills if condition.field=='skill' else facts.certificates
        observed={token(v) for v in values};expected={token(v) for v in condition.expected}
        prefix='skills' if condition.field=='skill' else 'certificates'
        matched=set();supporting=[]
        for wanted in expected:
            paths=[f'{prefix}.{i}' for i,value in enumerate(values) if token(value)==wanted]
            if paths and not any(qualified(source.quote) for path in paths for source in facts.field_sources[path]):matched.add(wanted);supporting.extend(paths)
        met=expected<=matched if condition.operator=='contains_all' else bool(matched)
        paths=sorted(set(supporting)) if met else [f'{prefix}.{i}' for i in range(len(values))]
        return ('met' if met else 'unknown'),{'observed':values,'matched':sorted(matched)},'EXACT_FACT_TOKEN_MET' if met else 'MISSING_OR_UNCONFIRMED_FACT',paths
