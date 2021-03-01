import requests
from bs4 import BeautifulSoup

if __name__ == '__main__':
    rs = requests.get("https://dungeon.su/spells/")
    soup = BeautifulSoup(rs.text)
    uls = soup.findAll('ul','list-of-items')
    count = 0
    for ul in uls:
        if len(ul.contents)<100:
            continue
        topics = ul.contents
        for topic in topics:
            if count>=100:
                break
            if len(topic)<2:
                continue
            count+=1
            url = "https://dungeon.su"+list(topic)[2].attrs['href']
            print(url)
            rs1 = requests.get(url)
            page = BeautifulSoup(rs1.text)
            with open('page'+str(count)+'.html', 'w', encoding='utf-8') as f:
                f.write(str(page))
            with open('index.txt', 'a', encoding='utf-8') as f:
                f.write(str(count)+": "+url+"\n")
            
        break
