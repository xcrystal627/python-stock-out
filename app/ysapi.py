# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime
import re
import xml.etree.ElementTree as ET
from retry import retry
import urllib.parse
import uuid
from dataclasses import dataclass
from typing import List, Optional, Tuple
import json
from json import JSONDecodeError
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from logging import Logger
import const
from apireq import APIRequests

os.environ['WDM_LOG_LEVEL'] = '0'
os.environ['WDM_LOCAL'] = '1'
os.environ['WDM_PRINT_FIRST_LINE'] = 'False'


@dataclass
class YahooAPIAuth:
    authorization_code: str
    access_token: str
    refresh_token: str


@dataclass
class OrderListData:
    order_id: str


@dataclass
class OrderInfoItemData:
    item_id: str
    title: str


@dataclass
class OrderInfoData:
    order_id: str
    order_status: int
    items: List[OrderInfoItemData]


@dataclass
class GetStockData:
    item_code: str
    status: int
    quantity: int


@dataclass
class SetStockResponseData:
    item_code: str
    quantity: int


@dataclass
class SetStockData:
    item_code: str
    quantity: int


class YahooBaseError(Exception):
    pretext = ''

    def __init__(self, message, *args):
        if self.pretext:
            message = f"{self.pretext}: {message}"
        super().__init__(message, *args)


class YahooAPIError(YahooBaseError):
    pretext = 'Yahoo API エラー'


class YahooAuthWebDriverError(YahooBaseError):
    pretext = '認証webdriverエラー'


class YahooAuthError(YahooBaseError):
    pretext = '接続エラー'


class YahooShoppingApiError(YahooBaseError):
    pretext = 'ショッピングAPIエラー'


class YahooWebDriver:
    def __init__(self,
                 profile_dir: str,
                 headless: bool = True):
        self.headless = headless
        self.profile_dir = profile_dir

        self.driver: Optional[webdriver.Chrome] = None
        self.yahoo_business_id: Optional[str] = None
        self.yahoo_business_password: Optional[str] = None
        self.yahoo_id: Optional[str] = None
        self.yahoo_password: Optional[str] = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @retry(tries=3, delay=3, backoff=2, jitter=1)
    def setup(self,
              business_id: str,
              business_password: str,
              yahoo_id: str,
              yahoo_password: str):

        self.yahoo_business_id = business_id
        self.yahoo_business_password = business_password
        self.yahoo_id = yahoo_id
        self.yahoo_password = yahoo_password

        try:
            # driver初期化
            self._init()
        except Exception:
            self.close()
            raise YahooAuthWebDriverError('driver setup error')

    def _init(self):
        if self.driver:
            return

        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--blink-settings=imagesEnabled=false')
        options.add_argument('--disable-extensions')
        # options.add_argument('--start-maximized')
        options.add_argument('--log-level=3')

        os.makedirs(self.profile_dir, exist_ok=True)
        options.add_argument('--user-data-dir=' + self.profile_dir)

        driver = None
        try:
            driver = webdriver.Chrome(
                ChromeDriverManager().install(),
                options=options)
            driver.implicitly_wait(1)
            driver.set_page_load_timeout(60)
            driver.set_script_timeout(60)
            driver.get('https://www.yahoo.co.jp/')
            WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located)
        except Exception:
            if driver is not None:
                driver.close()
                driver.quit()
            raise YahooAuthWebDriverError('Failed to init driver error occurred Exception')

        self.driver = driver

    def close(self):
        try:
            if self.driver:
                self.driver.close()
                self.driver.quit()
        except Exception:
            raise
        finally:
            self.driver = None

    def get_page(self, url):
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 30).until(EC.presence_of_all_elements_located)
        except Exception:
            raise YahooAuthWebDriverError('Failed to get page due to occurred exception error')


class YahooAuth:
    def __init__(self,
                 api: APIRequests,
                 profile_dir: str,
                 application_id: str,
                 secret: str,
                 auth_file: str,
                 log: Logger,
                 business_id: str,
                 business_password: str,
                 yahoo_id: str,
                 yahoo_password: str,
                 ):
        self.api: APIRequests = api
        self.profile_dir: str = profile_dir
        self.application_id = application_id
        self.secret = secret
        self.authz_code: Optional[str] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.log: Logger = log
        self.business_id = business_id
        self.business_password = business_password
        self.yahoo_id = yahoo_id
        self.yahoo_password = yahoo_password
        self.auth_file = auth_file

        self._load_auth()
        self.update_token()

    def _get_az_code(self):
        with YahooWebDriver(profile_dir=self.profile_dir, headless=const.DRIVER_HEADLESS) as driver:
            try:
                driver.setup(business_id=self.business_id,
                             business_password=self.business_password,
                             yahoo_id=self.yahoo_id,
                             yahoo_password=self.yahoo_password)
            except Exception:
                self.log.exception('Failed to setup webdriver')
                raise YahooAuthError('Failed to setup webdriver')

            query = urllib.parse.urlencode({
                'response_type': 'code',
                'client_id': self.application_id,
                'redirect_uri': const.YJDN_CALLBACK_URL,
                'scope': 'openid+profile',
                'nonce': str(uuid.uuid4()),
            }, safe='+')
            url_p = urllib.parse.urlparse(
                'https://auth.login.yahoo.co.jp/yconnect/v2/authorization')._replace(
                query=query)
            url = url_p.geturl()

            try:
                driver.get_page(url)
            except Exception:
                self.log.exception('Failed to goto auth page')
                raise YahooAuthError('Failed to goto auth page')

            try:
                if len(driver.driver.find_elements(by=By.XPATH, value='//input[@id="username" and @readonly]')) <= 0:
                    driver.driver.find_element(by=By.XPATH, value='//input[@id="username"]').send_keys(self.yahoo_id)
                    driver.driver.find_element(by=By.XPATH, value='//*[@id="btnNext"]').click()
                    time.sleep(1)

                driver.driver.find_element(by=By.XPATH, value='//*[@id="passwd"]').send_keys(self.yahoo_password)
                time.sleep(1)
                previous_url = driver.driver.current_url
                driver.driver.find_element(by=By.XPATH, value='//*[@id="btnSubmit"]').click()
                WebDriverWait(driver.driver, 30).until(lambda driver_: driver.driver.current_url != previous_url)

                #
                if len(driver.driver.find_elements(
                        by=By.XPATH,
                        value='//*[@id="itemPermissionMode"]//*[@id=".save" and @type="submit"]')) > 0:
                    driver.driver.find_element(
                        by=By.XPATH,
                        value='//*[@id="itemPermissionMode"]//*[@id=".save" and @type="submit"]').click()
                    WebDriverWait(driver.driver, 30).until(lambda driver_: driver.driver.current_url != previous_url)

            except Exception:
                self.log.exception('Failed to login')
                raise YahooAuthError('Failed to login')

            try:
                query = urllib.parse.urlparse(driver.driver.current_url).query
                queries = urllib.parse.parse_qs(query)
                # noinspection PyTypeChecker
                az_code = queries['code'][0]
            except Exception:
                self.log.exception('Failed to get authorization code')
                raise YahooAuthError('Failed to get authorization code due to not found index in array')

            self.authz_code = az_code

    def _get_access_token(self):
        headers = {
            'Host': 'auth.login.yahoo.co.jp',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.application_id,
            'client_secret': self.secret,
            'redirect_uri': const.YJDN_CALLBACK_URL,
            'code': self.authz_code,
        }
        url = 'https://auth.login.yahoo.co.jp/yconnect/v2/token'
        try:
            res = self.api.request_post(url=url, headers=headers, data=data)
            if res.status_code != 200:
                return False
            res_json = res.json()
            self.access_token = res_json["access_token"]
            self.refresh_token = res_json["refresh_token"]
        except Exception:
            self.log.exception('Failed to request to get access token')
            raise YahooAuthError('Failed to request to get access token')

    def _clear_auth(self):
        self.authz_code = None
        self.access_token = None
        self.refresh_token = None

    def _load_auth(self):
        self._clear_auth()
        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file) as f:
                    data = json.load(f)
                    self.authz_code = data.get('authorization_code', None)
                    self.access_token = data.get('access_token', None)
                    self.refresh_token = data.get('refresh_token', None)
            except JSONDecodeError:
                self.log.info('yahoo auth file is not json file')
                # jsonファイルで無い場合は、再認証
                pass
            except Exception:
                self.log.exception('can not open yahoo auth file')
                raise YahooAuthError('can not open yahoo auth file')

    def _output_auth_file(self):
        data = {
            'authorization_code': self.authz_code,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
        }
        try:
            os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
            with open(self.auth_file, 'w') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            self.log.exception('Failed to output auth file')
            raise YahooAuthError('Failed to output auth file')

    def re_auth(self):
        try:
            self._get_az_code()
            self._get_access_token()
            self._output_auth_file()
        except Exception:
            self.log.exception('Failed to get az code')
            raise YahooAuthError('Failed to get az code')

    @retry(tries=3, delay=3, backoff=2, jitter=1)
    def update_token(self):
        if not self.refresh_token:
            self.log.debug('exec auth due to not set refresh token')
            self.re_auth()
            return

        headers = {
            'Host': 'auth.login.yahoo.co.jp',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.application_id,
            'client_secret': self.secret,
            'refresh_token': self.refresh_token,
        }
        url = 'https://auth.login.yahoo.co.jp/yconnect/v2/token'
        try:
            res = self.api.request_post(url=url, headers=headers, data=data)
        except Exception:
            self.log.exception('Failed to request to get access token')
            raise YahooAuthError('Failed to request to get access token')

        if res.status_code != 200:
            self.log.debug('Failed to update access token message=%s', res.text)
            if 'invalid_grant' not in res.text:
                raise YahooAuthError('Failed to update access token not invalid grant')
            self.log.debug('exec auth due to invalid grant')
            self.re_auth()
            return

        try:
            res_json = res.json()
            self.access_token = res_json["access_token"]
        except Exception:
            self.log.exception('Failed to get access token')
            raise YahooAuthError('Failed to get access token')

        try:
            self._output_auth_file()
        except Exception:
            self.log.exception('Failed to output auth file')
            raise YahooAuthError('Failed to output auth file')


class OrderListAPI:
    def __init__(self,
                 api: APIRequests,
                 auth: YahooAuth,
                 log: Logger):
        self.api = api
        self.auth = auth
        self.log = log

    @retry(tries=3, delay=2, backoff=2, jitter=1)
    def get(self,
            order_time_from: datetime,
            order_time_to: datetime,
            result_count: Optional[int] = 2000) -> List[OrderListData]:

        url = "https://circus.shopping.yahooapis.jp/ShoppingWebService/V1/orderList" \
            if const.IS_PRODUCTION else 'https://test.circus.shopping.yahooapis.jp/ShoppingWebService/V1/orderList'

        headers = {
            'HTTP-Version': 'http_version',
            'Authorization': f'Bearer {self.auth.access_token}',
            'Host': 'circus.shopping.yahooapis.jp' if const.IS_PRODUCTION else 'test.circus.shopping.yahooapis.jp',
        }
        data = f"""
           <Req>
               <Search>
                   <Result>{result_count}</Result>
                   <Start></Start>
                   <Sort>+order_time</Sort>
                   <Condition>
                       <OrderTimeFrom>{order_time_from.strftime('%Y%m%d%H%M%S')}</OrderTimeFrom>
                       <OrderTimeTo>{order_time_to.strftime('%Y%m%d%H%M%S')}</OrderTimeTo>
                   </Condition>
                   <Field>OrderId,OrderTime,IsYahooAuctionOrder</Field>
               </Search>
               <SellerId>{YahooAPI.seller_id}</SellerId>
           </Req>
           """
        root_post = ET.fromstring(data)
        root_post.set('version', '1.0')
        root_post.set('encoding', 'UTF-8')

        item_count = 1
        total_count = 1
        order_list = []
        while item_count <= total_count:
            # リクエスト
            post_data = ET.tostring(element=root_post, encoding="utf-8", method='xml')
            try:
                res = self.api.request_post(url=url, headers=headers, data=post_data)
                if res.status_code != 200:
                    if res.status_code == 401:
                        www_auth = res.headers.get('WWW-Authenticate', '')
                        re_ = re.search(r'error="(?P<error_msg>[a-zA-Z_]+)"', www_auth)
                        if re_:
                            error_msg = re_.group('error_msg')
                            if error_msg in ['invalid_token']:
                                self.log.debug('Token refresh in OrderListAPI.get')
                                self.auth.update_token()
                                raise YahooShoppingApiError('Failed to post request due to invalid token')

                    root_res = ET.fromstring(res.text)
                    error_code = root_res.find('.//Code').text if root_res.findall('.//Code') else ''
                    error_msg = root_res.find('.//Message').text if root_res.findall('.//Message') else ''
                    if error_code == 'px-04102':
                        self.log.debug('Re auth in OrderListAPI.get')
                        self.auth.re_auth()
                    raise YahooShoppingApiError(
                        f'Failed to post request due to AccessToken has been expired code={error_code}, message={error_msg}')
            except Exception:
                self.log.exception('Failed to post request get order list')
                raise YahooShoppingApiError('Failed to post request to get order list')

            root_response = ET.fromstring(res.text)
            for el_order_info in root_response.findall('.//OrderInfo'):
                # OrderId取得
                order_id = el_order_info.find('.//OrderId').text

                order_data = OrderListData(order_id=order_id)
                order_list.append(order_data)

            # 総数更新
            total_1 = root_response.find('.//TotalCount').text
            if total_1:
                total_count = int(total_1)

            # 開始位置をxmlに反映
            item_count += result_count
            root_post.find('.//Start').text = str(item_count)

        return order_list


class OrderInfoAPI:
    def __init__(self,
                 api: APIRequests,
                 auth: YahooAuth,
                 log: Logger):
        self.api = api
        self.auth = auth
        self.log = log

    @retry(tries=3, delay=2, backoff=2, jitter=1)
    def get(self, order_id: str) -> List[OrderInfoData]:
        if not order_id:
            return []

        data = f"""
            <Req>
                <Target>
                    <OrderId>{order_id}</OrderId>
                    <Field>OrderId,OrderStatus,ItemId,Title</Field>
                </Target>
                <SellerId>{YahooAPI.seller_id}</SellerId>
            </Req>
            """
        root_post = ET.fromstring(data)
        root_post.set('version', '1.0')
        root_post.set('encoding', 'UTF-8')

        url = "https://circus.shopping.yahooapis.jp/ShoppingWebService/V1/orderInfo" \
            if const.IS_PRODUCTION else 'https://test.circus.shopping.yahooapis.jp/ShoppingWebService/V1/orderInfo'
        headers = {
            'HTTP-Version': 'http_version',
            'Authorization': f'Bearer {self.auth.access_token}',
            'Host': 'circus.shopping.yahooapis.jp' if const.IS_PRODUCTION else 'test.circus.shopping.yahooapis.jp'
        }
        post_data = ET.tostring(element=root_post, encoding="utf-8", method='xml')
        try:
            res = self.api.request_post(url=url, headers=headers, data=post_data)
            if res.status_code != 200:
                if res.status_code == 401:
                    www_auth = res.headers.get('WWW-Authenticate', '')
                    re_ = re.search(r'error="(?P<error_msg>[a-zA-Z_]+)"', www_auth)
                    if re_:
                        error_msg = re_.group('error_msg')
                        if error_msg in ['invalid_token']:
                            self.log.debug('Token refresh in OrderInfoAPI.get')
                            self.auth.update_token()
                            raise YahooShoppingApiError('Failed to post request due to invalid token')

                root_res = ET.fromstring(res.text)
                error_code = root_res.find('.//Code').text if root_res.findall('.//Code') else ''
                error_msg = root_res.find('.//Message').text if root_res.findall('.//Message') else ''
                if error_code == 'px-04102':
                    self.log.debug('Re auth in OrderInfoAPI.get')
                    self.auth.re_auth()
                raise YahooShoppingApiError(
                    f'Failed to post request due to AccessToken has been expired code={error_code}, message={error_msg}')
        except Exception:
            self.log.exception('Failed to post request get order info list')
            raise YahooShoppingApiError('Failed to post request to get order info list')

        root_response = ET.fromstring(res.text)
        order_info_list = []
        for el_order_info in root_response.findall('.//OrderInfo'):
            order_id_ = el_order_info.find('.//OrderId').text
            order_status = int(el_order_info.find('.//OrderStatus').text)
            order_items = []
            for el_item in el_order_info.findall('.//Item'):
                item_id = el_item.find('.//ItemId').text
                title = el_item.find('.//Title').text
                order_item_data = OrderInfoItemData(item_id=item_id,
                                                    title=title)
                order_items.append(order_item_data)

            order_inf_data = OrderInfoData(order_id=order_id_,
                                           order_status=order_status,
                                           items=order_items)
            order_info_list.append(order_inf_data)

        return order_info_list


class OrderAPI:
    def __init__(self,
                 api: APIRequests,
                 auth: YahooAuth,
                 log: Logger):
        self.api = api
        self.auth = auth
        self.log = log

        # 注文検索API
        self.list = OrderListAPI(api=api, auth=auth, log=log)
        # 注文詳細API
        self.info = OrderInfoAPI(api=api, auth=auth, log=log)


class StockAPI:
    def __init__(self,
                 api: APIRequests,
                 auth: YahooAuth,
                 log: Logger):
        self.api = api
        self.auth = auth
        self.log = log

    @retry(tries=3, delay=2, backoff=2, jitter=1)
    def get(self, item_codes: List[str], chunk_size: int = 1000) -> List[GetStockData]:
        if not item_codes:
            return []

        url = "https://circus.shopping.yahooapis.jp/ShoppingWebService/V1/getStock" \
            if const.IS_PRODUCTION else 'https://test.circus.shopping.yahooapis.jp/ShoppingWebService/V1/getStock'

        headers = {
            'HTTP-Version': 'http_version',
            'Authorization': f'Bearer {self.auth.access_token}',
            'Host': 'circus.shopping.yahooapis.jp' if const.IS_PRODUCTION else 'test.circus.shopping.yahooapis.jp'
        }

        # 重複を作雄j
        item_codes = list(set(item_codes))
        # リストを分割
        item_codes_n = [item_codes[i:i + chunk_size] for i in range(0, len(item_codes), chunk_size)]
        stock_list = []
        for item_codes_1 in item_codes_n:
            post_data = {
                'seller_id': YahooAPI.seller_id,
                'item_code': ','.join(item_codes_1)
            }

            try:
                res = self.api.request_post(url=url, headers=headers, data=post_data)
                if res.status_code != 200:
                    if res.status_code == 401:
                        www_auth = res.headers.get('WWW-Authenticate', '')
                        re_ = re.search(r'error="(?P<error_msg>[a-zA-Z_]+)"', www_auth)
                        if re_:
                            error_msg = re_.group('error_msg')
                            if error_msg in ['invalid_token']:
                                self.log.debug('Token refresh in StockAPI.get')
                                self.auth.update_token()
                                raise YahooShoppingApiError('Failed to post request due to invalid token')

                    root_res = ET.fromstring(res.text)
                    error_code = root_res.find('.//Code').text if root_res.findall('.//Code') else ''
                    error_msg = root_res.find('.//Message').text if root_res.findall('.//Message') else ''
                    raise YahooShoppingApiError(
                        f'Failed to post request code={error_code}, message={error_msg}')
            except Exception:
                self.log.exception('Failed to post request to get stock')
                raise YahooAuthError('Failed to post request to get stock')

            root_response = ET.fromstring(res.text)

            for el_item in root_response.findall('.//Result'):
                item_code = el_item.find('.//ItemCode').text
                status = el_item.find('.//Status').text
                if status == '1':
                    quantity = el_item.find('.//Quantity').text
                    if quantity == '':
                        # 在庫無限大は、-1にする
                        quantity = -1
                    else:
                        quantity = int(quantity)

                    stock_data = GetStockData(item_code=item_code,
                                              status=int(status),
                                              quantity=quantity)
                    stock_list.append(stock_data)

        return stock_list

    @retry(tries=3, delay=2, backoff=2, jitter=1)
    def set(self, set_stock_list: List[SetStockData]) -> List[SetStockResponseData]:
        if not set_stock_list:
            return []

        item_codes = []
        quantities = []
        for set_stock_data in set_stock_list:
            item_codes.append(set_stock_data.item_code)
            quantities.append(str(set_stock_data.quantity))

        post_data = {
            'seller_id': YahooAPI.seller_id,
            'item_code': ','.join(item_codes),
            'quantity': ','.join(quantities),
        }
        url = "https://circus.shopping.yahooapis.jp/ShoppingWebService/V1/setStock" \
            if const.IS_PRODUCTION else 'https://test.circus.shopping.yahooapis.jp/ShoppingWebService/V1/setStock'

        headers = {
            'HTTP-Version': 'http_version',
            'Authorization': f'Bearer {self.auth.access_token}',
            'Host': 'circus.shopping.yahooapis.jp' if const.IS_PRODUCTION else 'test.circus.shopping.yahooapis.jp'
        }

        try:
            res = self.api.request_post(url=url, headers=headers, data=post_data)
            if res.status_code != 200:
                if res.status_code == 401:
                    www_auth = res.headers.get('WWW-Authenticate', '')
                    re_ = re.search(r'error="(?P<error_msg>[a-zA-Z_]+)"', www_auth)
                    if re_:
                        error_msg = re_.group('error_msg')
                        if error_msg in ['invalid_token']:
                            self.log.debug('Token update in StockAPI.set')
                            self.auth.update_token()
                            raise YahooShoppingApiError('Failed to post request due to invalid token')

                root_res = ET.fromstring(res.text)
                error_code = root_res.find('.//Code').text if root_res.findall('.//Code') else ''
                error_msg = root_res.find('.//Message').text if root_res.findall('.//Message') else ''
                raise YahooShoppingApiError(
                    f'Failed to post request code={error_code}, message={error_msg}')
        except Exception:
            self.log.exception('Failed to post request to set stock')
            raise YahooAuthError('Failed to post request to set stock')

        root_response = ET.fromstring(res.text)
        stock_list = []
        for el_item in root_response.findall('.//Result'):
            item_code = el_item.find('.//ItemCode').text
            quantity = el_item.find('.//Quantity').text
            if quantity is not None:
                if quantity == '':
                    # 空白は在庫無限大。-1にする
                    quantity = -1
                else:
                    quantity = int(quantity)

                stock_data = SetStockResponseData(item_code=item_code,
                                                  quantity=quantity)
                stock_list.append(stock_data)

        return stock_list


class ShoppingAPI:
    def __init__(self,
                 api: APIRequests,
                 auth: YahooAuth,
                 log: Logger):
        self.order = OrderAPI(api=api, auth=auth, log=log)
        self.stock = StockAPI(api=api, auth=auth, log=log)


class YahooAPI:
    seller_id = const.YSHOP_SELLER_ID

    def __init__(self,
                 profile_dir: str,
                 application_id: str,
                 secret: str,
                 auth_file: str,
                 business_id: str,
                 business_password: str,
                 yahoo_id: str,
                 yahoo_password: str,
                 log: Logger,
                 retry_total: int = 5,
                 backoff_factor: int = 2,
                 connect_timeout: float = 30.0,
                 read_timeout: float = 60.0,
                 cert: Optional[Tuple[str, str]] = None,
                 ):
        self.profile_dir = profile_dir
        self.log = log
        self.api = APIRequests(retry_total=retry_total,
                               backoff_factor=backoff_factor,
                               connect_timeout=connect_timeout,
                               read_timeout=read_timeout,
                               cert=cert)
        # yahooID連携
        self.auth = YahooAuth(api=self.api,
                              profile_dir=self.profile_dir,
                              application_id=application_id,
                              secret=secret,
                              auth_file=auth_file,
                              log=self.log,
                              business_id=business_id,
                              business_password=business_password,
                              yahoo_id=yahoo_id,
                              yahoo_password=yahoo_password)
        # ショッピングAPI
        self.shopping = ShoppingAPI(api=self.api, auth=self.auth, log=self.log)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.api.close()
