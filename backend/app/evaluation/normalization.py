"""可重放规范化：精确别名、日期精度区间与不重复的经历覆盖。"""
import calendar
from datetime import date
from decimal import Decimal,localcontext,ROUND_FLOOR,ROUND_CEILING
from types import MappingProxyType
import re,unicodedata
from app.evaluation.schemas import EducationValue,MajorResolution,ExperienceBounds,Employment

NORMALIZATION_REVISION='screening-core-v1'
MAJOR_REVISION='core-major-v1'


def token(value: str|None) -> str:
    """统一宽度、大小写和空白，保留+/#/标点以区分C、C++和C#。"""
    return ' '.join(unicodedata.normalize('NFKC',value or '').strip().casefold().split())


_EDUCATION_GROUPS={
    'high_school':(1,['高中','普通高中','高中毕业','high school']),
    'secondary':(1,['中专','中等专业学校','中专毕业','secondary']),
    'associate':(2,['大专','专科','大学专科','大专毕业','associate','associate degree']),
    'bachelor':(3,['本科','大学本科','本科学历','本科毕业','已取得本科学历','学士','工学学士','理学学士','bachelor','bachelor degree',"bachelor's degree",'bachelor of science','bachelor of engineering']),
    'master':(4,['硕士','硕士研究生','硕士毕业','master','master degree',"master's degree"]),
    'doctor':(5,['博士','博士研究生','博士毕业','doctor','doctoral degree','phd','ph.d.']),
}
_EDUCATION=MappingProxyType({token(alias):EducationValue(code,rank) for code,(rank,aliases) in _EDUCATION_GROUPS.items() for alias in [code,*aliases]})
_MAJOR_GROUPS={
    'computer_science':['计算机科学与技术','计算机科学','computer science'],
    'software_engineering':['软件工程','software engineering'],
    'computer_application_technology':['计算机应用技术'],
    'software_technology':['软件技术'],
    'artificial_intelligence':['人工智能','artificial intelligence'],
    'electronic_information':['电子信息工程','electronic information engineering'],
    'automation':['自动化','automation'],
    'accounting':['会计学','会计','accounting'],
    'finance':['金融学','金融','finance'],
    'mechanical_engineering':['机械工程','mechanical engineering'],
    'mechanical_design_manufacturing_automation':['机械设计制造及其自动化'],
    'business_administration':['工商管理','business administration'],
}
_MAJORS=MappingProxyType({token(alias):code for code,aliases in _MAJOR_GROUPS.items() for alias in [code,*aliases]})
MAJOR_DICTIONARIES=MappingProxyType({MAJOR_REVISION:_MAJORS})


class EducationNormalizer:
    """精确学历别名；在读、混合或否定描述不自动挑一个较高层次。"""
    def normalize(self,value: str|None) -> EducationValue|None:
        """返回已知层次；是否已取得由教育日期/状态单独判断。"""
        return _EDUCATION.get(token(value))


class MajorNormalizer:
    """词典扩展须新增revision，旧岗位评估可按原revision重放。"""
    def resolve(self,value: str|None,dictionary_revision: str) -> MajorResolution:
        """CS、计算机相关等模糊值不做子串匹配，也不伪造置信度。"""
        if dictionary_revision not in MAJOR_DICTIONARIES:raise ValueError('Unknown major dictionary revision')
        canonical=MAJOR_DICTIONARIES[dictionary_revision].get(token(value))
        return MajorResolution(canonical,Decimal(1) if canonical else Decimal(0),canonical is None)


def ongoing(value):
    """只识别明确的至今标记，不将缺失结束日期擅自当作仍在职。"""
    return token(value) in {'至今','现在','present','current','ongoing'}


def date_bounds(value: str|None) -> tuple[date,date]|None:
    """年/月/日分别保留精度范围；不猜测歧义斜杠日月顺序。"""
    raw=token(value)
    patterns=[r'([0-9]{4})',r'([0-9]{4})[-./年]([0-9]{1,2})月?',r'([0-9]{4})[-./年]([0-9]{1,2})[-./月]([0-9]{1,2})日?']
    for pattern in patterns:
        match=re.fullmatch(pattern,raw)
        if not match:continue
        values=[int(v) for v in match.groups()]
        try:
            year=values[0]
            if len(values)==1:return date(year,1,1),date(year,12,31)
            month=values[1]
            if len(values)==2:return date(year,month,1),date(year,month,calendar.monthrange(year,month)[1])
            day=date(year,month,values[2]);return day,day
        except ValueError:return None
    return None


def _month_floor(value):return value.year*12+value.month-1
def _month_ceil(value):return _month_floor(value)+(value.day>1)


def _union_months(intervals):
    end=None;total=0
    for left,right in sorted(intervals):
        if right<=left:continue
        if end is None or left>=end:total+=right-left;end=right
        elif right>end:total+=right-end;end=right
    return total


def _years(months,rounding):
    with localcontext() as ctx:
        ctx.prec=50
        return (Decimal(months)/12).quantize(Decimal('0.000001'),rounding=rounding)


class ExperienceCalculator:
    """输入由调用方确认相关的经历；只计算时间，不推断岗位相关性。"""
    def bounds(self,employment: list[Employment],as_of: date) -> ExperienceBounds|None:
        """上下界分别做区间并集，缺失/颠倒/未来日期不假装为零。"""
        if type(as_of) is not date:raise ValueError('A frozen date is required')
        if not employment:return None
        lower=[];upper=[]
        for value in employment:
            entry=Employment.model_validate(value)
            start=date_bounds(entry.start_date)
            end=(as_of,as_of) if ongoing(entry.end_date) else date_bounds(entry.end_date)
            if start is None or end is None or start[0]>end[1] or start[1]>as_of or end[1]>as_of:return None
            if start[0]==start[1]==end[0]==end[1]:continue
            lower.append((_month_ceil(start[1]),_month_floor(end[0])))
            upper.append((_month_floor(start[0]),_month_ceil(end[1])))
        return ExperienceBounds(_years(_union_months(lower),ROUND_FLOOR),_years(_union_months(upper),ROUND_CEILING))

    def relevant_years(self,employment: list[Employment],as_of: date) -> Decimal|None:
        """仅返回无歧义月年限；有精度范围时为None，规则可单独使用bounds证明。"""
        result=self.bounds(employment,as_of)
        return result.min_years if result is not None and result.min_years==result.max_years else None
