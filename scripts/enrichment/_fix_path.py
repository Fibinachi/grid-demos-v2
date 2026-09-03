import re, sys
path = sys.argv[1]
c = open(path).read()
c = re.sub(r'OUTPUT_DIR = .*', 'OUTPUT_DIR = "/home/ec2-user/data/denom_scrape"', c)
open(path, 'w').write(c)
print("fixed:", path)
