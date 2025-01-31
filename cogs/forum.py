from os.path import exists, getsize
from bs4 import BeautifulSoup
from typing import List
import aiohttp
import json

DOMAIN = "donanimhaber.com"
FORUMS_FILE_NAME = "forums.json"


def main() -> None:
  print(getid("/apple-iphone-firsatlari-tum-modeller-ana-konu--121084032?isLink=true"))
  print(format("/apple-iphone-firsatlari-tum-modeller-ana-konu--121084032?isLink=true"))
  # Put your tests here


def getid(link: str) -> (int | str):
  try:
    dash = link.rfind("-")
    if dash == -1:
      raise ValueError(f"Couldn't find id of link: {link}")

    link = link[dash+1:]

    question = link.rfind("?")
    if question != -1:
      link = link[:question]
  except Exception as ex:
    raise Exception(f"getid/{link}/{ex}")
  
  try:
    return int(link)
  except ValueError:
    return link

def format(link: str) -> (str | None):
  question_index = link.rfind("?")
  dash_index = link.rfind("--")
  if question_index != -1 and question_index > dash_index:
    return link[:question_index]


class Subforum():
  subforum_list: List["Subforum"] = []


  def __init__(self) -> None:
    self.id = None
    self.channels = None
    self.latest = None
    self.title = None
    Subforum.subforum_list.append(self)
  

  def remove(self) -> None:
    Subforum.subforum_list.remove(self)
    del self
    Subforum.save_subforums()


  async def get_subforum_info(self, link, channels=[], latest=0, title=None) -> None:
    if await isvalid(link):
      self.id = getid(link)
      self.channels: List[int] = channels
      self.latest: int = latest
      self.title: str = title                                          # Title is actually loaded when checking for new posts so we don't request the same page twice
      Subforum.subforum_list.append(self)
    else:
      raise ValueError("Invalid forum link")


  async def check_posts(self) -> List["ForumPost"]:
    posts = []
    latest_ids = []

    async with aiohttp.ClientSession() as session:
      async with session.get(f'https://forum.donanimhaber.com/placeholder--{self.id}') as response:
        soup = BeautifulSoup(await response.text(),"html.parser")

        if self.title is None:
          self.title = soup.title.text[:soup.title.text.find(" Forumları")]
        
        try:
          post_divs = soup(class_="kl-icerik-satir yenikonu",limit=15) # Look at the top 15 posts
        except Exception as e:
          raise Exception(f"check_posts/creating post divs/{e}")

        for post in post_divs:
          try:
            post_href: str = post.select_one("a").get("href")               # Get the href, for example: /shopflix-guvenilir-mi--155719413
          except Exception as e:
            raise Exception(f"check_posts/creating post divs/{e}")
          
          if int(getid(post_href)) > self.latest:
            if format(post_href) is not None:
              post_href = format(post_href)
            try:
              latest_ids.append(int(getid(post_href)))
              posts.append(await ForumPost.create(post_href))
            except Exception as e:
              raise Exception(f"check_posts/\"{self.id} {post_href}\"/{e}")

          # This is for diagnostics
          # print(f"post href: {getid(post_href)}, self.latest: {self.latest}, should the post be added: {int(getid(post_href))>self.latest}")



    if len(latest_ids) != 0:
      self.latest = max(latest_ids)
      Subforum.save_subforums()

    return posts


  async def add_channel(channel_id, link) -> int:
    if link is None:
      return 1
    id = getid(link)

    for subforum in Subforum.subforum_list:
      if subforum.id == id:
        if id in subforum.channels:
          return 2
        else:
          subforum.channels.append(channel_id)
          Subforum.save_subforums()
          return 0

    try:
      await Subforum.create(link)
      Subforum.save_subforums()
      return 0
    except ValueError:
      return 1


  async def remove_channel(channel_id, link:str= None) -> int:
    if link is None:
      for subforum in Subforum.subforum_list:
        if channel_id in subforum.channels:
          subforum.channels.remove(channel_id)

      Subforum.save_subforums()
      return 0

    else:
      for subforum in Subforum.subforum_list:
        if subforum.id == getid(link):
          if channel_id in subforum.channels:
            subforum.channels.remove(channel_id)

            Subforum.save_subforums()
            return 1

    return 2


  @classmethod
  def load_from_file(cls, id, channels=[], latest=0, title=None) -> None:
    subforum = Subforum()
    subforum.id = id
    subforum.channels = channels
    subforum.latest = latest
    subforum.title = title


  @classmethod
  def load_subforums(cls) -> list["Subforum"]:
    if exists(FORUMS_FILE_NAME) and getsize(FORUMS_FILE_NAME) != 0:        # If the .json file does exist, it loads in the data from that file.
      with open(FORUMS_FILE_NAME,"r") as json_file:
        for subforum_data in json.load(json_file):
          Subforum.load_from_file(id=subforum_data['id'],channels=subforum_data['channels'],
                  latest=int(subforum_data['latest']),title=subforum_data['title'])
    else:
      with open(FORUMS_FILE_NAME,"w") as json_file:
        json.dump([],json_file)


  @classmethod
  def save_subforums(cls) -> None:
    save_file = []

    for subforum in Subforum.subforum_list:
      save_file.append({"id": subforum.id, "channels": subforum.channels, "latest": subforum.latest, "title": subforum.title})

    with open(FORUMS_FILE_NAME,"w") as json_file:
      json.dump(save_file,json_file, indent=2)
  

  @classmethod
  async def create(cls, link) -> None:  # Got to use this to create new objects because of stupid async logic
    subforum = Subforum()
    await subforum.get_subforum_info(link=link)
    return subforum
  
  
  @classmethod
  async def get_list(cls, id) -> List["Subforum"]:
    result = []
    for subforum in Subforum.subforum_list:
      if id in subforum.channels:
        result.append(subforum)
    
    return result


class ForumPost():
  def __init__(self, href) -> None:
    self.href = href
    self.title = None
    self.author = None
    self.avatar = None
    self.content = None


  @classmethod
  async def create(cls, href) -> None:  # Got to use this to create new objects because of stupid async logic x2
    forumpost = ForumPost(href)
    await forumpost.get_post_info()
    return forumpost


  async def get_post_info(self) -> None:
    async with aiohttp.ClientSession() as session:
      async with session.get(f'https://forum.donanimhaber.com{self.href}') as response:
        try:
          soup = BeautifulSoup(await response.text(),"html.parser")
        except Exception as e:
          raise Exception(f"ForumPost/{e}")
        
        try:
          self.title = soup.find("h1",class_="kl-basligi upInfinite").text.strip()
        except Exception as e:
          raise Exception(f"ForumPost/title/{e}")
        
        try:
          author_info = soup.find("aside",class_="ki-cevapsahibi")
          self.author = author_info.find("div",class_="ki-kullaniciadi member-info").find("a").find("b").text
        except Exception as e:
          raise Exception(f"ForumPost/author/{e}")

        try:
          self.avatar = author_info.find("div",class_="content-holder").find("a",class_="ki-avatar").find("img").attrs["src"]
        except AttributeError:
          pass

        try:
          # The easiest way to get the post content seems to be through this element, but this element consists of a very large json file
          # And since it wouldn't make sense to parse everything just to get one thing we just use string manipulation
          # The added +14 and -3 are to remove some extra characters that index() leaves in
          content_jsons = soup.findAll(name="script",type="application/ld+json")
          content_json = content_jsons[-1].text
          content_start = content_json.index("articleBody")+14
          content_end =  content_json.index("articleS")-3
          self.content = content_json[content_start:content_end].strip()

        except Exception as e:
          raise Exception(f"ForumPost/content/{e}")

async def isvalid(link) -> bool:  # Checks if the link leads to a valid DonanımHaber forum
  if DOMAIN in link:
    try:
      async with aiohttp.ClientSession() as session:
        async with session.get(link) as response:
          return response.status == 200

    except aiohttp.ClientError:
      return False

  return False

if __name__ == '__main__':
  main()