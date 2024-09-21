from urllib.parse import urlparse

class CookieStorage(object):
  cookies_ : dict = {}

  def __init__(self):
    pass

  def load_from_array(self, cookies_arr):
    self.cookies_ = {}
    self.add_cookies(cookies_arr)

  def add_cookies(self, add_cookies, alt_domain = None):
    for el in add_cookies :
      add_domain = el['domain'] if 'domain' in el else alt_domain
      if add_domain not in self.cookies_ :
        self.cookies_[add_domain] = {}
      self.cookies_[add_domain][el['name']] = el

  def merge_url_cookies(self, url, actual_cookies):
    """
    Clear all cookies for url and up domains and replace it with actual_cookies
    """
    url_domain = urlparse(url).hostname
    print("url_domain <" + str(url_domain) + ">, url <" + str(url) + ">")
    url_domain_parts = url_domain.split('.')
    for i in range(len(url_domain_parts) - 1) :
      search_domain = ".".join(url_domain_parts[i : ])
      print("POP <" + str(search_domain) + ">")
      self.cookies_.pop(search_domain, None)
      self.cookies_.pop('.' + search_domain, None)

    self.add_cookies(actual_cookies, alt_domain = url_domain)

  def as_array(self):
    ret = []
    for domain, name_to_cookies in self.cookies_.items() :
      for name, cookie in name_to_cookies.items() :
        ret.append(cookie)
    return ret

  def fetch_iframes_for_cookies_(self, driver, depth = 0):
    iframes = driver.find_elements_by_xpath("//iframe")
    for index, iframe in enumerate(iframes):
      # Your sweet business logic applied to iframe goes here.
      driver.switch_to.frame(index)
      print(" " * (depth + 1) + "Process frame #" + str(index) + " with url = " + driver.current_url)
      merge_cookies = driver.get_cookies()
      self.merge_url_cookies(driver.current_url, merge_cookies)
      self.fetch_iframes_for_cookies_(driver, depth = depth + 1)
      driver.switch_to.parent_frame()

  def merge_driver_cookies(self, driver):
    cur_window = driver.current_window_handle
    # choosen frame will not be reverted
    pages = driver.window_handles
    for page in pages :
      driver.switch_to.window(page)
      print("merge_driver_cookies: Process window with url = " + driver.current_url)
      merge_cookies = driver.get_cookies()
      self.merge_url_cookies(driver.current_url, merge_cookies, depth = 0)
      self.fetch_iframes_for_cookies_(driver)
    driver.switch_to.window(cur_window)

"""
if __name__ == "__main__":
  cookie_storage = CookieStorage()
  cookie_storage.load_from_array([
    { 'domain' : 'okaif.ru', 'name' : 'TEST1' },
    { 'domain' : 'a.okaif.ru', 'name' : 'TEST2' },
    { 'domain' : '.okaif.ru', 'name' : 'TEST3' }])

  arr = cookie_storage.as_array()
  print("STEP 1: " + str(arr))

  cookie_storage.merge_url_cookies('https://okaif.ru', [{'domain' : 'okaif.ru', 'name' : 'TEST4'}])
  arr =	cookie_storage.as_array()
  print("STEP 2: " + str(arr))
"""
