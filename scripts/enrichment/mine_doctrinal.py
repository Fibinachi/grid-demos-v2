"""Mine doctrinal signals from pastor names and titles."""
import csv, re, sqlite3
from collections import Counter

d = r'E:\grid'
pastors = list(csv.DictReader(open(d + '/irs_pastors.csv', encoding='utf-8-sig')))

# Common male and female first names for gender inference
MALE_NAMES = {
    'james','john','robert','michael','william','david','richard','joseph','thomas',
    'charles','christopher','daniel','matthew','anthony','mark','donald','steven','paul',
    'andrew','joshua','kenneth','kevin','brian','george','timothy','ronald','edward',
    'jason','jeffrey','ryan','jacob','gary','nicholas','eric','jonathan','stephen',
    'larry','justin','scott','brandon','benjamin','samuel','gregory','frank','raymond',
    'alexander','patrick','jack','dennis','jerry','tyler','aaron','jose','nathan',
    'henry','douglas','peter','adam','zachary','walter','kyle','harold','carl',
    'gerald','roger','keith','jeremy','terry','willie','jesse','ralph','billy',
    'bruce','danny','roy','wayne','eugene','randy','vincent','russell','howard',
    'allen','jimmy','johnny','phillip','craig','albert','arthur','fred','willis',
    'leslie','calvin','ernest','glenn','marvin','leonard','clarence','edwin','todd',
    'martin','andre','curtis','brent','duane','tommy','byron','earl','elmer',
    'floyd','gene','grover','herbert','homer','irvin','jimmie','karl','lloyd',
    'lonnie','louie','luther','melvin','milton','morris','neal','nelson','otis',
    'percy','philip','raymond','rex','rodney','ross','ruben','rufus','shelby',
    'sidney','silas','sonny','sylvester','theodore','tracy','vernon','virgil',
    'wade','warren','wilbert','wilbur','wiley','willard','wilmer','buddy',
    'bob','don','jim','joe','tom','bill','dick','george','hank','jack','sam',
    'ben','mike','dan','dave','ed','frank','guy','jake','jay','joe','kurt',
    'lee','lou','mack','nick','noah','sam','skip','stan','tim','tony','van',
    'walt','ward','abe','alfred','amos','angelo','arnold','austin','barry',
    'barton','benedict','blake','brad','bradley','brett','cameron','chad',
    'clark','claude','clayton','clifford','clifton','clint','cole','conrad',
    'dallas','dana','darrell','darren','daryl','dean','delbert','demetrius',
    'derek','derrick','dewayne','dewitt','dominick','donnie','doris','doyle',
    'drew','duncan','dustin','dwayne','earnest','edgar','edison','elbert',
    'elijah','elisha','elton','emanuel','emerson','emery','emmitt','errol',
    'ezekiel','ezra','felix','fernando','forrest','foster','francis','freddy',
    'fredrick','gabriel','garland','garrett','garry','gavin','gordon','grady',
    'graham','grant','gregg','gustavo','hans','harlan','harley','harrison',
    'harvey','hayward','hector','hilton','hugh','hugo','ian','ignacio','isaac',
    'isaiah','isiah','israel','ivan','ivory','jabari','jace','jackie','jaden',
    'jamel','jarrod','javier','jedidiah','jed','jerald','jerrod','jessie',
    'joel','johnathan','johnnie','jonah','jonas','jordan','julian','julius',
    'kareem','keith','kelvin','ken','kendall','kenny','kent','kermit','kerry',
    'kirk','kristopher','kurtis','lamar','lance','landon','laurence','lawrence',
    'leland','lenny','leopold','leroy','les','levi','linwood','lionel','loren',
    'lorenzo','lovie','lowell','loyd','lucas','luciano','lucius','luke',
    'lyle','lyman','lynn','malcolm','malik','manuel','marc','marcellus',
    'marcos','marcus','mario','marion','marquis','marshall','miles','milford',
    'mitch','mitchell','monte','monty','mose','moses','moshe','murray','myles',
    'myron','napoleon','nathaniel','neil','newton','nolan','norbert','norman',
    'norris','odon','oliver','ollie','omar','orlando','orval','oscar','oswald',
    'owen','paris','percy','perry','pete','phil','pierce','porter','prince',
    'quentin','quincy','quin','rafael','raleigh','randal','randell','randolph',
    'rashad','raul','reed','reese','reginald','reid','reuben','rex','reynold',
    'rhett','ricardo','rick','ricky','riley','robert','roberto','rocky',
    'rod','roderick','rodolfo','rodrigo','roel','rogelio','roland','rolando',
    'roman','romero','ron','ronnie','roosevelt','rory','roscoe','rudolf',
    'rudolph','rudy','rupert','russel','rusty','ryan','ryder','salvador',
    'sammy','samson','samuel','sandy','santiago','santo','saul','scot',
    'scott','scottie','sean','sebastian','sergio','seth','seymour','shane',
    'shannon','shaun','shaw','shawn','shelby','sheldon','sherman','shirley',
    'silas','simon','solomon','sonny','spencer','stacey','stanford','stanley',
    'stefan','stephen','sterling','steve','steven','stewart','stuart','sydney',
    'tad','tanner','tate','taylor','ted','terence','terrance','terrell',
    'terrence','terry','thad','thaddeus','theo','theodore','theron','thomas',
    'tien','tim','timmy','timothy','titus','tobias','toby','todd','tom',
    'tomas','tommy','tony','tracy','travis','tremayne','trent','trenton',
    'trevor','troy','truman','tucker','ty','tyler','tyrone','tyson','ulysses',
    'val','vance','vaughn','vern','vernon','vicente','vick','victor','vincent',
    'vinson','virgil','virgle','vito','wade','waldo','walker','wallace',
    'walt','walter','ward','warner','warren','waylon','wayne','wilber',
    'wilbur','wiley','wilford','wilfred','will','willard','william','willie',
    'willis','wilmer','wilson','wilton','winford','wing','winifred','winston',
    'woodrow','wyatt','wynn','xavier','zachariah','zachary','zane','zeke',
}

FEMALE_NAMES = {
    'mary','patricia','jennifer','linda','barbara','elizabeth','susan','jessica',
    'sarah','karen','lisa','nancy','betty','margaret','sandra','ashley','dorothy',
    'kimberly','emily','donna','michelle','carol','amanda','melissa','deborah',
    'stephanie','rebecca','sharon','laura','cynthia','kathleen','amy','angela',
    'helen','anna','brenda','pamela','nicole','emma','samantha','katherine',
    'christine','debra','rachel','carolyn','janet','catherine','maria','heather',
    'diane','ruth','julie','joyce','virginia','olivia','kelly','lauren','christina',
    'joan','evelyn','judith','andrea','megan','cheryl','alice','jean','doris',
    'ann','martha','frances','kathryn','gloria','tiffany','theresa','shirley',
    'mildred','rose','janice','jane','julia','sara','gail','denise','marilyn',
    'amber','madison','teresa','beverly','kathy','tammy','irene','debbie',
    'lillian','april','diana','carrie','charlotte','monica','katie','bonnie',
    'peggy','lynn','renee','paula','crystal','dana','annie','phyllis','lori',
    'lynda','bernice','bertha','bessie','beulah','billie','blanche','bobbie',
    'bridget','caitlin','candace','candice','carla','carmen','carole','caroline',
    'cassandra','cecelia','celeste','charity','charlene','chelsea','cheri',
    'cherie','chrystal','cindy','clair','clara','claudette','claudia','cleo',
    'colleen','connie','constance','cora','corina','corinne','cornelia','courtney',
    'cristina','daisy','darlene','dawn','deana','deann','deanna','deirdre',
    'delilah','della','delores','deloris','desiree','dianna','dianne','dixie',
    'dollie','dolly','dolores','dominique','dona','donna','dora','doreen',
    'doris','dorothea','dorothy','dorthy','edith','edna','edwina','eileen',
    'elaine','eleanor','elenor','elisa','elise','eliza','ella','ellen','elsie',
    'elva','emilia','emilie','emily','emma','enid','erica','erika','erma',
    'ernestine','estelle','ester','esther','etta','eula','eunice','eva','evangelina',
    'evangeline','eve','fannie','fawn','felecia','fern','flora','florence',
    'flossie','francine','frankie','freda','freida','frieda','gabriela','gabrielle',
    'genevieve','georgia','georgiana','geraldine','gertrude','gina','ginger',
    'gladys','glenda','glenna','goldie','grace','gracie','greta','gretchen',
    'guadalupe','gwen','gwendolyn','haley','hanna','hannah','harriet','hazel',
    'heather','heidi','helen','helena','henrietta','hilary','hilda','holly',
    'hope','ida','imogene','inez','inga','irma','isabel','isabella','ivy',
    'jackie','jacquelin','jacqueline','jacquelyn','jaime','jamie','jan',
    'jana','jane','janell','janelle','janet','janette','janie','janine',
    'janis','jannie','jasmine','jayne','jean','jeanie','jeanine','jeannette',
    'jeannie','jeannine','jeffie','jena','jenifer','jennie','jennifer','jenny',
    'jeraldine','jeri','jerri','jerrie','jerry','jess','jesse','jessica',
    'jessie','jewel','jewell','jill','jo','joan','joann','joanna','joanne',
    'jocelyn','jodi','jodie','jody','johanna','jolene','jolie','joni',
    'jordan','josephine','josie','joy','joyce','juana','juanita','judi',
    'judie','judith','judy','julia','juliana','juliann','julianne','julie',
    'juliet','juliette','june','justina','justine','kaitlin','kaitlyn',
    'karen','kari','karin','karina','karla','karyn','kasey','katarina',
    'kate','katelyn','katherine','katheryn','kathie','kathleen','kathrine',
    'kathryn','kathy','katie','katina','katrina','kay','kayla','kaylee',
    'keisha','kelli','kellie','kelly','kelsey','kendra','kerri','kerry',
    'kim','kimberlee','kimberley','kimberly','kira','kirsten','krista',
    'kristen','kristi','kristie','kristin','kristina','kristine','kristy',
    'krystal','krystle','lacey','laci','lacy','ladonna','lakesha','lakeisha',
    'lana','latasha','latisha','latonya','laura','lauralee','lauren','laurette',
    'laurie','laverne','lavonne','lawanda','leah','lean','leann','leanna',
    'leanne','leatha','leatrice','lee','leigh','leila','lena','lenora',
    'leola','leona','leonie','leonor','leonora','lesa','lesley','leslie',
    'lessie','leta','leticia','letitia','leva','lewanda','lexie','lia',
    'libby','lidia','lila','lilia','lilian','liliana','lillian','lillie',
    'lilly','lily','lina','linda','lindsay','lindsey','lindy','lisa',
    'lisabeth','lisette','liz','liza','lizbeth','lizzie','lois','lola',
    'lolita','lona','lora','loraine','lorena','lorene','loretta','lori',
    'lorie','lorinda','lorine','lorraine','lottie','lou','louella','louisa',
    'louise','loula','louvenia','love','lovella','lovie','luann','lucile',
    'lucille','lucinda','lucretia','lucy','luella','lula','lulu','luna',
    'lupe','luz','lydia','lyla','lyn','lynda','lynette','lynn','lynne',
    'lynnette','lynsy','mabel','mable','madalyn','maddie','madeleine',
    'madeline','madelyn','madge','mae','maegan','magdalena','maggie',
    'maida','maira','maisie','mamie','manda','mandy','manuela','mara',
    'marcella','marci','marcia','marcie','marcille','mare','maretta',
    'margaret','margarita','margery','margie','margo','margot','margret',
    'marguerite','mari','maria','mariah','marian','mariana','mariann',
    'marianne','maribeth','maricela','marie','marietta','marilee','marilyn',
    'marina','mario','marion','marisa','marisol','marissa','marjorie',
    'markita','marla','marlana','marleen','marlene','marlie','marlyn',
    'marlys','marni','marquita','marshall','marta','martha','martina',
    'marva','marvel','mary','maryann','maryanne','marybelle','maryellen',
    'maryjane','marylou','marylyn','masako','matilda','mattie','maud',
    'maude','maureen','maura','maurene','maurine','maxine','may',
    'maya','maybell','mayme','mayra','mazie','mckenzie','meagan',
    'megan','meggan','meghan','melanie','melinda','melisa','melissa',
    'melodie','melody','melva','melvina','mendy','mercedes','mercy',
    'meredith','merilyn','merle','merlene','merna','merri','merrie',
    'merrilee','merry','michaela','michele','michelle','micki','mickie',
    'miguelina','mika','miki','mikki','mildred','milissa','millicent',
    'millie','milly','mimi','mina','mindi','mindy','minerva','minna',
    'minnie','minta','mira','miranda','miriam','missy','misty','mitzi',
    'molly','mona','monica','monika','monique','monta','moorea',
    'morgan','moriah','mossie','muriel','myra','myrna','myrtice','myrtle',
    'na','nadine','nancy','nanette','nannette','nannie','naoma','naomi',
    'natalia','natalie','natasha','nathalie','natosha','necia','nella',
    'nellie','neoma','nettie','neva','newell','nichole','nicki','nicole',
    'nicolette','nikki','nila','nina','nita','noel','noelle','noemi',
    'nola','noma','nona','norah','noreen','norma','nova','novella',
}

# Also collect female-pattern titles
FEMALE_TITLES = ['sister', 'sr.', 'sra.', 'nun', 'mother', 'mrs.', 'ms.']

def classify(title, denom=''):
    t = title.strip()
    tl = t.lower()
    
    # Extract first name
    first = ''
    first_words = re.findall(r"^[A-Za-z]+|[A-Z][a-z]+", t)
    for w in first_words:
        if w.lower() not in ('rev','reverend','pastor','bishop','father','minister','dr','sister','brother','mother','mrs','ms','mr','honorable'):
            first = w
            break
    
    first_lower = first.lower()
    
    # Gender
    gender = 'unknown'
    if first_lower in MALE_NAMES:
        gender = 'male'
    elif first_lower in FEMALE_NAMES:
        gender = 'female'
    else:
        for ft in FEMALE_TITLES:
            if ft in tl:
                gender = 'female'
                break
    
    # Title type
    title_type = 'unknown'
    if any(w in tl for w in ['rev','reverend']):
        title_type = 'reverend'
    elif 'pastor' in tl:
        title_type = 'pastor'
    elif 'bishop' in tl:
        title_type = 'bishop'
    elif 'father' in tl:
        title_type = 'father'
    elif 'minister' in tl:
        title_type = 'minister'
    elif 'dr' in tl or 'doctor' in tl:
        title_type = 'doctor'
    elif 'sister' in tl or 'nun' in tl:
        title_type = 'sister'
    elif 'brother' in tl:
        title_type = 'brother'
    elif 'mother' in tl:
        title_type = 'mother'
    
    # Egalitarian vs complementarian inference
    doctrinal = 'unknown'
    if gender == 'female' and title_type in ('pastor','reverend','minister','bishop'):
        doctrinal = 'egalitarian'
    elif gender == 'male' and denom and any(k in denom.lower() for k in ['catholic','orthodox','southern baptist','sbc','lcms','wels','pca','independent baptist']):
        doctrinal = 'complementarian'
    elif gender == 'male':
        doctrinal = 'complementarian_likely'
    
    return {
        'full_name': t,
        'first_name': first,
        'gender': gender,
        'title_type': title_type,
        'doctrinal_inferred': doctrinal,
    }

# Process all pastors
results = []
stats = Counter()

for p in pastors:
    info = classify(p['pastor_ico'])
    info['church_name'] = p['church_name']
    info['ein'] = p['ein']
    info['state'] = p['state']
    results.append(info)
    stats[info['gender']] += 1
    stats[info['title_type']] += 1
    stats[info['doctrinal_inferred']] += 1

print('Gender breakdown:')
for k, v in stats.most_common():
    if k in ('male','female','unknown'):
        print(f'  {k}: {v}')

print('\nTitle breakdown:')
for k, v in sorted(stats.items()):
    if k in ('pastor','reverend','bishop','father','minister','doctor','sister','brother','mother','unknown'):
        print(f'  {k}: {v}')

print('\nInferred doctrinal alignment:')
for k, v in sorted(stats.items()):
    if k in ('egalitarian','complementarian','complementarian_likely','unknown'):
        print(f'  {k}: {v}')

# Show sample of female pastors
print('\nFemale pastors sample:')
for r in results:
    if r['gender'] == 'female' and r['title_type'] in ('pastor','reverend'):
        print(f'  {r["full_name"][:40]} | {r["church_name"][:40]} | inferred: {r["doctrinal_inferred"]}')
        if sum(1 for x in results if x['gender'] == 'female' and x['title_type'] in ('pastor','reverend')) <= 10:
            break

# Save to SQLite
conn = sqlite3.connect(d + '/churches.db')
cur = conn.cursor()
updated_gender = 0
updated_doctrinal = 0
for r in results:
    if r['gender'] != 'unknown':
        cur.execute("UPDATE churches SET worship_style = CASE WHEN ? != 'unknown' AND (worship_style = '' OR worship_style IS NULL) THEN ? ELSE worship_style END WHERE ein = ?",
                    ('female_pastor' if r['gender']=='female' else 'male_pastor',
                     'female_pastor' if r['gender']=='female' else 'male_pastor',
                     r['ein']))
        if cur.rowcount:
            updated_gender += 1
    if r['doctrinal_inferred'] != 'unknown':
        cur.execute("UPDATE churches SET doctrinal_alignment = CASE WHEN ? != 'unknown' AND (doctrinal_alignment = '' OR doctrinal_alignment IS NULL) THEN ? ELSE doctrinal_alignment END WHERE ein = ?",
                    (r['doctrinal_inferred'], r['doctrinal_inferred'], r['ein']))
        if cur.rowcount:
            updated_doctrinal += 1

conn.commit()
print(f'\nSQLite updated: {updated_gender} gender, {updated_doctrinal} doctrinal')
conn.close()
