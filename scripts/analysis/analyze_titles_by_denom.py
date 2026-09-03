"""Cross-reference pastor titles with denominations."""
import csv, re
from collections import Counter, defaultdict

d = r'E:\grid'
pastors = list(csv.DictReader(open(d + '/irs_pastors.csv', encoding='utf-8-sig')))
irs = list(csv.DictReader(open(d + '/irs_churches.csv', encoding='utf-8-sig')))

GROUP_DENOMS = {
    '0000': 'Independent', '0168': 'Assemblies of God', '0343': 'Baptist General Conf',
    '0384': 'CMA', '0450': 'Church of God (Cleveland)', '0461': 'Church of God (Anderson)',
    '0470': 'Nazarene', '0596': 'Evangelical Covenant', '0597': 'EvFree',
    '0731': 'Free Methodist', '0928': 'LCMS', '0930': 'ELCA',
    '0951': 'Mennonite', '0975': 'United Methodist', '1060': 'PCUSA',
    '1061': 'PCA', '1082': 'RCA', '1120': 'Salvation Army',
    '1126': 'SDA', '1181': 'SBC', '1190': 'UCC',
    '1250': 'WELS', '1259': 'Wesleyan', '1320': 'American Baptist',
    '1350': 'Episcopal', '1474': 'COGIC', '1489': 'ACNA',
    '1588': 'Assemblies of God', '1619': 'United Methodist', '1620': 'United Methodist',
    '1678': 'Catholic', '1709': 'SBC', '1800': 'ELCA',
    '2358': 'PCUSA', '3125': 'LCMS', '9386': 'Catholic',
}

ein_group = {r.get('EIN',''): r.get('GROUP','') for r in irs}

MALE = {'james','john','robert','michael','william','david','richard','joseph','thomas','charles','christopher','daniel','matthew','anthony','mark','donald','steven','paul','andrew','joshua','kenneth','kevin','brian','george','timothy','ronald','edward','jason','jeffrey','ryan','jacob','gary','nicholas','eric','jonathan','stephen','larry','justin','scott','brandon','benjamin','samuel','gregory','frank','raymond','alexander','patrick','jack','dennis','jerry','tyler','aaron','jose','nathan','henry','douglas','peter','adam','zachary','walter','kyle','harold','carl','gerald','roger','keith','jeremy','terry','willie','jesse','ralph','billy','bruce','danny','roy','wayne','eugene','randy','vincent','russell','howard','allen','jimmy','johnny','phillip','craig','albert','arthur','fred','calvin','ernest','glenn','marvin','leonard','clarence','edwin','todd','martin','curtis','brent','duane','tommy','byron','earl','luther','melvin','milton','nelson','otis','theodore','vernon','warren','wilbert','mack','nick','noah','skip','tim','tony','austin','barry','blake','brad','bradley','brett','cameron','chad','clark','claude','dean','derek','derrick','dustin','elijah','ezra','felix','foster','francis','gabriel','gordon','graham','grant','isaac','isaiah','joel','jordan','julian','levi','luke','miles','moses','nathaniel','neil','nolan','norman','oliver','oscar','owen','reed','riley','salvador','sammy','saul','sean','sebastian','seth','shane','shawn','simon','solomon','spencer','stanley','stuart','tanner','taylor','toby','travis','trent','trevor','troy','tyrone','victor','xavier','zachary'}

FEMALE = {'mary','patricia','jennifer','linda','barbara','elizabeth','susan','jessica','sarah','karen','lisa','nancy','betty','margaret','sandra','ashley','dorothy','kimberly','emily','donna','michelle','carol','amanda','melissa','deborah','stephanie','rebecca','sharon','laura','cynthia','kathleen','amy','angela','helen','anna','brenda','pamela','nicole','emma','samantha','katherine','christine','debra','rachel','carolyn','janet','catherine','maria','heather','diane','ruth','julie','joyce','virginia','olivia','kelly','lauren','christina','joan','evelyn','judith','andrea','megan','cheryl','alice','jean','doris','ann','martha','frances','kathryn','gloria','tiffany','theresa','shirley','janice','julia','sara','gail','denise','marilyn','amber','madison','teresa','beverly','kathy','tammy','irene','debbie','lillian','april','diana','carrie','charlotte','monica','katie','bonnie','peggy','lynn','renee','paula','crystal','dana','annie','phyllis','lori','carla','carmen','cassandra','cindy','clara','constance','courtney','daisy','dawn','deanna','dolores','edith','edna','eileen','elaine','eleanor','elisa','ella','ellen','elsie','erica','esther','eva','faith','florence','georgia','geraldine','gina','ginger','gladys','glenda','grace','gretchen','gwen','haley','hannah','harriet','hazel','heidi','hilary','holly','hope','ida','isabel','isabella','ivy','jackie','jacqueline','jaime','jamie','jana','jane','janice','jasmin','jasmine','jean','jeanne','jenna','jennifer','jenny','jessica','jill','joan','joanna','jocelyn','jodi','jody','johanna','jolene','josie','joy','joyce','juana','juanita','judith','judy','julia','juliana','julie','june','justine','karen','kari','karina','karla','kate','katherine','kathleen','kathryn','kathy','katie','katrina','kay','kayla','kaylee','keisha','kelli','kellie','kelly','kelsey','kendra','kerri','kerry','kim','kimberly','krista','kristen','kristi','kristin','kristina','kristine','kristy','krystal','lacey','laura','lauren','laurie','leah','lee','leigh','lena','lesley','leslie','leticia','lidia','lilian','lillian','lillie','lilly','lily','linda','lindsay','lindsey','lisa','lois','lola','lorena','loretta','lori','lorraine','louise','luann','lucille','lucy','lydia','lynn','mabel','madeline','madison','mae','maggie','mandy','marcia','margaret','margie','margo','maria','mariah','marian','marie','marilyn','marion','marissa','marjorie','marla','marlene','martha','martina','mary','matilda','maureen','maxine','may','megan','melanie','melinda','melissa','melody','meredith','michele','michelle','mildred','millie','mindy','miranda','miriam','misty','mitzi','molly','mona','monica','monique','morgan','myra','myrna','nadine','nancy','naomi','natalia','natalie','natasha','nellie','nettie','nicole','nikki','nina','nita','noelle','nora','norma','olivia','pam','pamela','patricia','paula','peggy','penny','phyllis','rachel','rebecca','renee','rhonda','rita','roberta','robin','rosa','rose','rosemary','rosie','roxanne','ruby','ruth','sabrina','sadie','sally','samantha','sandra','sandy','sara','sarah','shannon','sharon','shawna','sheila','shelby','sherri','sherry','sheryl','shirley','sonia','sophia','sophie','stacey','stacy','stella','stephanie','sue','susan','susie','suzanne','sylvia','tabitha','tamara','tami','tammie','tammy','tanya','tara','tasha','taylor','teresa','terri','terry','tessa','thelma','theresa','tiffany','tina','toni','tonya','tori','tracey','traci','tracy','trina','trisha','valerie','vanessa','velma','vera','veronica','vicki','vickie','vicky','victoria','viola','violet','virginia','vivian','wanda','wendy','whitney','wilma','yolanda','yvette','yvonne','zoe'}

title_by_denom = defaultdict(lambda: Counter())
male_by_denom = Counter()
female_by_denom = Counter()

for p in pastors:
    ein = p['ein']
    group = ein_group.get(ein, '')
    denom = GROUP_DENOMS.get(group, f'Group {group}')
    
    ico = p['pastor_ico'].upper()
    
    title = 'unknown'
    if re.search(r'\b(REV|REVEREND)\b', ico): title = 'REVEREND'
    elif 'PASTOR' in ico: title = 'PASTOR'
    elif 'BISHOP' in ico: title = 'BISHOP'
    elif 'FATHER' in ico: title = 'FATHER'
    elif 'MINISTER' in ico: title = 'MINISTER'
    elif 'DOCTOR' in ico or ' DR ' in ico: title = 'DOCTOR'
    elif 'MOTHER' in ico: title = 'MOTHER'
    elif 'SISTER' in ico: title = 'SISTER'
    elif 'BROTHER' in ico: title = 'BROTHER'
    
    title_by_denom[denom][title] += 1
    
    first = ''
    for w in re.findall(r"[A-Z][a-z]+", ico):
        wl = w.lower()
        if wl not in ('rev','reverend','pastor','bishop','father','minister','dr','doctor','sister','brother','mother','mrs','ms','mr','honorable','saint','st','jr','sr','ii','iii','iv'):
            first = wl
            break
    
    if first in MALE: male_by_denom[denom] += 1
    elif first in FEMALE: female_by_denom[denom] += 1

print('=== Title distribution by denomination (groups with 20+) ===')
print()
for denom in sorted(title_by_denom.keys()):
    titles = title_by_denom[denom]
    total = sum(titles.values())
    if total < 20: continue
    top = titles.most_common(3)
    mc = male_by_denom.get(denom, 0)
    fc = female_by_denom.get(denom, 0)
    pct = fc / (mc + fc) * 100 if (mc + fc) > 0 else 0
    tstr = ' | '.join(f'{t}:{c}' for t,c in top)
    print(f'{denom:30s} n={total:>4} | {tstr} | {pct:3.0f}% F')

# Also show female pastors by denomination
print('\n=== Female pastors by denomination (top 15) ===')
for denom, c in sorted(female_by_denom.items(), key=lambda x: -x[1])[:15]:
    mc = male_by_denom.get(denom, 0)
    pct = c / (mc + c) * 100 if (mc + c) > 0 else 0
    print(f'  {denom:30s} {c:>3} female ({pct:.0f}%)')

# Show bishop distribution
print('\n=== BISHOP title by denomination ===')
bishop_denoms = Counter()
for p in pastors:
    if 'BISHOP' in p['pastor_ico'].upper():
        group = ein_group.get(p['ein'], '')
        denom = GROUP_DENOMS.get(group, f'Group {group}')
        bishop_denoms[denom] += 1
for d, c in bishop_denoms.most_common(10):
    print(f'  {d:30s} {c}')
