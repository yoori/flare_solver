import logging
import platform
import sys
import time
import json
import logging
import os
import sys
import functools
import random
import base64
import datetime

from datetime import timedelta
from urllib.parse import unquote

from func_timeout import FunctionTimedOut, func_timeout
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait

import certifi

import flare_solver.utils
import flare_solver.chromedriver_utils

# Image processing imports
import cv2
import numpy as np
import uuid

_ACCESS_DENIED_TITLES = [
  # Cloudflare
  'Access denied',
  # Cloudflare http://bitturk.net/ Firefox
  'Attention Required! | Cloudflare'
]

_ACCESS_DENIED_SELECTORS = [
  # Cloudflare
  'div.cf-error-title span.cf-code-label span',
  # Cloudflare http://bitturk.net/ Firefox
  '#cf-error-details div.cf-error-overview h1'
]

_CHALLENGE_TITLES = [
  # Cloudflare
  'Just a moment...',
  # DDoS-GUARD
  'DDoS-Guard'
]

_CHALLENGE_SELECTORS = [
  # Cloudflare
  '#cf-challenge-running', '.ray_id', '.attack-box', '#cf-please-wait', '#challenge-spinner', '#trk_jschal_js',
  # Custom CloudFlare for EbookParadijs, Film-Paleis, MuziekFabriek and Puur-Hollands
  'td.info #js_info',
  # Fairlane / pararius.com
  'div.vc div.text-box h2'
]

_SHORT_TIMEOUT = 1
_REDIRECT_WAIT_TIMEOUT = 5

"""
Request for process, can be extended and some custom fields used in process_command.
"""
class SolverRequest(object):
  url: str = None
  proxy: dict = None
  maxTimeout: float = 60 # timeout in sec
  cookies: dict = None

  def __init__(self, _dict = None):
    if _dict :
      self.__dict__.update(_dict)

"""
Response, can be extended and some custom fields used in process_command.
"""
class SolverResponse:
  url: str = None
  cookies: list = None
  userAgent: str = None

  def __init__(self, _dict):
    self.__dict__.update(_dict)

"""
Solver
"""
class Solver(object) :
  _proxy = None
  _driver = None
  _screenshot_i = 0

  def __init__(self, proxy = None) :
    self._proxy = proxy
    self._driver = None

  def save_screenshot(self, step_name) :
    screenshot_file_without_ext = str(self._screenshot_i) + '_' + step_name
    self._driver.save_screenshot(screenshot_file_without_ext + ".png")
    dom = self._driver.execute_script("return new XMLSerializer().serializeToString(document);")
    with open(screenshot_file_without_ext + '.html', 'w') as fp:
      fp.write(dom)
    self._screenshot_i += 1

  # Method that can overriden and process specific commands
  # It can return specific Response object (with additional fields for example)
  def process_command(self, res: SolverResponse, req: SolverRequest, driver: WebDriver):
    return res

  def solve(self, req: SolverRequest) -> SolverResponse:
    # do some validations
    if req.url is None:
      raise Exception("Request parameter 'url' is mandatory in 'request.get' command.")

    return self._resolve_challenge(req)

  def _resolve_challenge(self, req: SolverRequest) -> SolverResponse:
    driver = None
    start_time = datetime.datetime.now()
    try:
      try:
        user_data_dir = os.environ.get('USER_DATA', None)
        use_proxy = (req.proxy if req.proxy else self._proxy)
        driver = flare_solver.utils.get_webdriver(
          proxy = use_proxy,
          user_data_dir = user_data_dir,
          language = 'ru'
        )
        self._driver = driver
        logging.info('New instance of webdriver has been created to perform the request (proxy=' +
          str(use_proxy) + '), timeout = ' + str(req.maxTimeout))
        time.sleep(3) # Wait when driver will up

        if req.maxTimeout is not None :
          return func_timeout(req.maxTimeout, Solver._evil_logic, (self, req, driver, start_time))
        else :
          self._evil_logic(req, driver, start_time)

      except FunctionTimedOut as e :
        error_message = f'Error solving the challenge. Timeout after {req.maxTimeout} seconds. ' + str(e)
        logging.error(error_message)
        raise Exception(error_message)
      except Exception as e:
        error_message = 'Error solving the challenge. ' + str(e).replace('\n', '\\n')
        logging.error(error_message)
        raise Exception(error_message)

    finally:
      logging.info('Close webdriver')
      if driver is not None:
        driver.quit()
        logging.debug('A used instance of webdriver has been destroyed')

  @staticmethod
  def _click_verify(driver: WebDriver, click_coord):
    try:
      actions = ActionChains(driver)
      actions.move_by_offset(click_coord[0], click_coord[1]).click().perform()
      logging.debug("Cloudflare verify checkbox found and clicked!")
    except Exception:
      logging.debug("Cloudflare verify checkbox not found on the page.")

  @staticmethod
  def _check_timeout(req: SolverRequest, start_time: datetime.datetime, step_name: str):
    if req.maxTimeout is not None :
      now = datetime.datetime.now()
      wait_time_sec = (now - start_time).total_seconds()
      if wait_time_sec > req.maxTimeout :
        raise FunctionTimedOut("Timed out on " + step_name)

  def _evil_logic(self, req: SolverRequest, driver: WebDriver, start_time : datetime.datetime) -> SolverResponse:
    res = SolverResponse({})

    # navigate to the page
    logging.debug(f'Navigating to... {req.url}')
    driver.get(req.url)
    driver.start_session()  # required to bypass Cloudflare

    self.save_screenshot('evil_logic')

    # set cookies if required
    if req.cookies is not None and len(req.cookies) > 0:
      logging.debug(f'Setting cookies...')
      for cookie in req.cookies:
        driver.delete_cookie(cookie['name'])
        driver.add_cookie(cookie)
      # reload the page
      driver.get(req.url)
      driver.start_session()  # required to bypass Cloudflare

    # wait for the page
    if flare_solver.utils.get_config_log_html():
      logging.debug(f"Response HTML:\n{driver.page_source}")
    page_title = driver.title

    # find access denied titles
    for title in _ACCESS_DENIED_TITLES :
      if title == page_title:
        raise Exception('Cloudflare has blocked this request. '
          'Probably your IP is banned for this site, check in your web browser.')

    # find access denied selectors
    for selector in _ACCESS_DENIED_SELECTORS:
      found_elements = driver.find_elements(By.CSS_SELECTOR, selector)
      if len(found_elements) > 0:
        raise Exception('Cloudflare has blocked this request. '
          'Probably your IP is banned for this site, check in your web browser.')

    # find challenge by title
    challenge_found = False
    for title in _CHALLENGE_TITLES:
      if title.lower() == page_title.lower():
        challenge_found = True
        logging.info("Challenge detected. Title found: " + page_title)
        break

    if not challenge_found:
      # find challenge by selectors
      for selector in _CHALLENGE_SELECTORS:
        found_elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if len(found_elements) > 0:
          challenge_found = True
          logging.info("Challenge detected. Selector found: " + selector)
          break

    self.save_screenshot('after_challenge_check')

    if challenge_found:
      logging.info("Challenge detected, to solve it")

      html_element = None
      attempt = 0

      while True:
        Solver._check_timeout(req, start_time, "challenge loading wait")
        logging.info("Wait challenge loading, attempt #" + str(attempt))
        # Get screenshot of full page (all elements is in shadowroot)
        iframe_image = self._get_screenshot(driver)
        click_coord = Solver._get_flare_click_point(iframe_image)
        if click_coord :
          html_element = driver.find_element(By.TAG_NAME, "html")
          logging.info("Click by coords: " + str(click_coord[0]) + ", " + str(click_coord[1]))
          Solver._click_verify(driver, click_coord)
          break
        attempt = attempt + 1
        time.sleep(_SHORT_TIMEOUT)

      self.save_screenshot('after_verify_click')

      # waits until cloudflare redirection ends
      logging.info("Waiting for redirect")
      # noinspection PyBroadException
      try:
        WebDriverWait(driver, _REDIRECT_WAIT_TIMEOUT).until(staleness_of(html_element))
      except Exception:
        logging.info("Timeout waiting for redirect")

      self.save_screenshot('after_redirect_wait')
      logging.info("Challenge solved!")
      res.message = "Challenge solved!"
    else:
      self.save_screenshot('no_challenge_found')
      logging.info("Challenge not detected!")
      res.message = "Challenge not detected!"

    res.url = driver.current_url
    res.cookies = driver.get_cookies()
    logging.info("Cookies got")
    res.userAgent = flare_solver.utils.get_user_agent(driver)
    logging.info("User-Agent got")

    # Process specific command
    res = self.process_command(res, req, driver)

    self.save_screenshot('finish')
    logging.info('Solving finished')

    return res

  def _get_screenshot(self, driver) :
    png_buf = base64.b64decode(self._driver.get_screenshot_as_base64())
    png_np = np.frombuffer(png_buf, dtype = np.uint8)
    return cv2.imdecode(png_np, cv2.IMREAD_COLOR)

  @staticmethod
  def _get_flare_click_point(image) :
    image_height, image_width, _ = image.shape
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ret, mask = cv2.threshold(gray_image, 230, 255, 0)

    #cv2.imwrite('masked_image.png', mask) # Check that mask contains outer rect contour if colors will be changed
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    rect_contours = []
    for c in contours :
      x, y, w, h = cv2.boundingRect(c)

      # ignore small rectangles
      if w < 6 or h < 6 :
        continue

      sq = w * h / (image_height * image_width)

      # ignore very big rectangles
      if sq > 0.5 :
        continue

      # calculate area difference
      rect_area = w * h
      contour_area = cv2.contourArea(c)
      diff_area = abs(rect_area - contour_area)
      # eval iou with (with undestanding that contour_area inside rect_area)
      iou = contour_area / rect_area

      # get minimal contour (usualy we have here 3 contours
      if iou > 0.8:
        rect_contours.append((w * h, c))

    # Here 2 rect contours, each can be present as one or 2 contours
    """
    debug_image = image.copy()
    for rc in rect_contours :
      debug_image = cv2.drawContours(debug_image, [rc[1]], -1, (255, 0, 0), 1)
    cv2.imwrite('debug_rect_contours.png', debug_image)
    """

    rect_contours = sorted(rect_contours, key = lambda c_pair: c_pair[0])

    # pack low distance contours (one rect can be present as 2 contours : inner, outer)
    # remove buggest contour
    res_rect_contours = []
    prev_c_pair = None

    for c_pair in rect_contours : # go from lowest to biggest
      if prev_c_pair is None or abs(c_pair[0] - prev_c_pair[0]) / c_pair[0] > 0.5 :
        res_rect_contours.append(c_pair)
        prev_c_pair = c_pair

    rect_contours = res_rect_contours
    # rect contours sorted by area ascending

    """
    debug_image = image.copy()
    for rc in rect_contours :
      print("C: " + str(rc[0]))
      debug_image = cv2.drawContours(debug_image, [rc[1]], -1, (255, 0, 0), 1)
    cv2.imwrite('debug_packed_rect_contours.png', debug_image)
    """

    # Now we should find two rect contours (one inside other) with ratio 1-5%, (now I see : 0.0213)
    if len(rect_contours) > 1:
      area1 = rect_contours[0][0]
      for check_c in rect_contours[1:] :
        area2 = check_c[0]
        area_ratio = area1 / area2
        if area_ratio > 0.01 and area_ratio < 0.05 :
          # Found !
          x, y, w, h = cv2.boundingRect(rect_contours[0][1])
          return [random.randint(x + 2, x + w - 2), random.randint(y + 2, y + h - 2)]

    return None

# fix ssl certificates for compiled binaries
# https://github.com/pyinstaller/pyinstaller/issues/7229
# https://stackoverflow.com/questions/55736855/how-to-change-the-cafile-argument-in-the-ssl-module-in-python3
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

if __name__ == '__main__':
  sys.stdout.reconfigure(encoding = "utf-8")
  logging.basicConfig(format = '%(asctime)s [%(name)s] [%(levelname)s] : %(message)s',
    handlers = [logging.StreamHandler(sys.stdout)],
    level = logging.INFO)

  req = SolverRequest()
  req.url = 'https://knopka.ashoo.id'

  solver = Solver()
  res = solver.solve(req)
