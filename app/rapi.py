# -*- coding: utf-8 -*-

import base64
import xml.etree.ElementTree as ET
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import json
import zeep

from logging import Logger
import const
from apireq import APIRequests


@dataclass
class RakutenApiGetItemData:
    product_id: str
    item_name: Optional[str]
    item_price: Optional[int]
    inventory_count: Optional[int]


@dataclass
class OrderItemData:
    item_name: str
    manage_number: str


@dataclass
class OrderData:
    order_number: str
    order_progress: int
    order_items: List[OrderItemData]


@dataclass
class InventoryData:
    item_url: str
    inventory_count: int


@dataclass
class InventoryUpdateData:
    item_url: str
    inventory_count: int


@dataclass
class InventoryUpdateErrorResponseItemData:
    item_url: str
    error_code: str
    error_message: str


class RakutenAPIError(Exception):
    pretext = ''

    def __init__(self, message, *args):
        if self.pretext:
            message = f"{self.pretext}: {message}"
        super().__init__(message, *args)


class RakutenAPI:
    def __init__(self,
                 log: Logger,
                 retry_total: int = 5,
                 backoff_factor: int = 2,
                 connect_timeout: float = 30.0,
                 read_timeout: float = 60.0):
        self.api = APIRequests(retry_total=retry_total,
                               backoff_factor=backoff_factor,
                               connect_timeout=connect_timeout,
                               read_timeout=read_timeout)

        # 商品API
        self.item = RakutenItemAPI(api=self.api, log=log)
        # 注文API
        self.order = RakutenOrderAPI(api=self.api, log=log)
        # 在庫API
        self.inventory = RakutenInventoryAPI(log=log)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.api.close()

    @staticmethod
    def get_authz() -> bytes:
        b_service_secret = bytes(const.RMS_API_SERVICE_SECRET, encoding='utf-8')
        b_license_key = bytes(const.RMS_API_LICENSE_KEY, encoding='utf-8')
        return b"ESA " + base64.b64encode(b_service_secret + b':' + b_license_key)


class RakutenItemAPI:
    def __init__(self, api: APIRequests, log: Logger):
        self._api = api
        self.log = log

    def get(self, item_url: str) -> Optional[RakutenApiGetItemData]:
        headers = {
            'Authorization': RakutenAPI.get_authz(),
            'Content-Type': 'application/json; charset=utf-8',
        }
        payload = {
            "itemUrl": item_url
        }
        try:
            url = 'https://api.rms.rakuten.co.jp/es/1.0/item/get'
            response = self._api.request_get(url=url,
                                             headers=headers,
                                             payload=payload)
            if response.status_code != 200:
                self.log.error('Failed to post request to item get error=%s', response.text)
                raise RakutenAPIError('Failed to post request to item get status not 200')
        except Exception:
            self.log.exception('Failed to get request to get item')
            raise RakutenAPIError('Failed to get request to get item')

        root = ET.fromstring(response.text)
        status_code = root.find('.//itemGetResult/code').text
        if status_code != 'N000':
            return None

        if not root.findall('.//itemGetResult/item'):
            return None

        el_item = root.find('.//item')
        product_id = el_item.find('.//itemUrl').text
        item_name = el_item.find('.//itemName').text
        item_price = el_item.find('.//itemPrice').text

        inventory_count = 0
        for el_inventory in el_item.findall('.//itemInventory/inventories'):
            inventory_count = el_inventory.find('.//inventoryCount').text

        item_data = RakutenApiGetItemData(product_id=product_id,
                                          item_name=item_name,
                                          item_price=int(item_price),
                                          inventory_count=int(inventory_count))
        return item_data

    def update(self, item_url: str, inventory_count: int) -> bool:
        data = f"""<?xml version="1.0" encoding="UTF-8"?>
            <request>
                <itemUpdateRequest>
                    <item>
                        <itemUrl>{item_url}</itemUrl>
                        <itemInventory>
                            <inventoryType>1</inventoryType>
                            <inventories>
                                <inventory>
                                    <inventoryCount>{inventory_count}</inventoryCount>
                                </inventory>
                            </inventories>
                        </itemInventory>
                    </item>
                </itemUpdateRequest>
            </request>
            """

        # ET.dump(root)
        headers = {
            'Authorization': RakutenAPI.get_authz(),
            'content-type': 'text/xml; charset=utf-8',
        }
        try:
            url = 'https://api.rms.rakuten.co.jp/es/1.0/item/update'
            res = self._api.request_post(url=url,
                                         headers=headers,
                                         data=data)
            if res.status_code != 200:
                self.log.error('Failed to post request to item update error=%s', res.text)
                raise RakutenAPIError('Failed to post request to item update status not 200')
        except Exception:
            self.log.exception('Failed to post request to update item')
            raise RakutenAPIError('Failed to post request to update item')

        root = ET.fromstring(res.text)
        status_code = root.find('.//itemUpdateResult/code').text
        if status_code == 'N000':
            return False
        return True


class RakutenOrderAPI:
    def __init__(self, api: APIRequests, log: Logger):
        self._api = api
        self.log = log

    def search(self,
               start_datetime: datetime,
               end_datetime: datetime,
               item_count_per_page: int = 1000) -> List[str]:
        post_data = {
            "dateType": 1,
            "startDatetime": start_datetime.strftime('%Y-%m-%dT%H:%M:%S+0900'),
            "endDatetime": end_datetime.strftime('%Y-%m-%dT%H:%M:%S+0900'),
            "PaginationRequestModel": {
                "requestRecordsAmount": item_count_per_page,
                "requestPage": 1,
                "SortModelList": [
                    {
                        "sortColumn": 1,
                        "sortDirection": 1
                    }
                ]
            }
        }
        # url = https://api.rms.rakuten.co.jp/es/2.0/sample.order/searchOrder/
        url = 'https://api.rms.rakuten.co.jp/es/2.0/order/searchOrder/'
        headers = {
            'Authorization': RakutenAPI.get_authz(),
            'content-type': 'application/json; charset=utf-8',
        }

        page_count = 1
        total_pages = 1
        order_numbers = []
        while page_count <= total_pages:
            post_data['PaginationRequestModel']['requestPage'] = page_count
            try:
                res = self._api.request_post(url=url,
                                             headers=headers,
                                             data=json.dumps(post_data).encode('utf-8'))
                if res.status_code != 200:
                    self.log.error('Failed to post request to search order list error=%s', res.text)
                    raise RakutenAPIError('Failed to post request to search order list status not 200')
            except Exception:
                self.log.exception('Failed to post request to search order list')
                raise RakutenAPIError('Failed to post request to search order list')

            res_json = res.json()
            order_numbers.extend(res_json.get('orderNumberList', []))

            total_pages_1 = res_json.get('PaginationResponseModel', {}).get('totalPages')
            total_pages = 0 if not total_pages_1 else total_pages_1
            page_count += 1

        return order_numbers

    def get(self, order_number_list: List[str], chunk_size: int = 100) -> List[OrderData]:
        # リストを分割
        order_number_list_n = [order_number_list[i:i + chunk_size]
                               for i in range(0, len(order_number_list), chunk_size)]

        url = 'https://api.rms.rakuten.co.jp/es/2.0/order/getOrder/'
        headers = {
            'Authorization': RakutenAPI.get_authz(),
            'content-type': 'application/json; charset=utf-8',
        }

        orders = []
        for order_number_list_1 in order_number_list_n:
            post_data = {
                'orderNumberList': order_number_list_1,
                'version': 5,
            }
            try:
                res = self._api.request_post(url=url,
                                             headers=headers,
                                             data=json.dumps(post_data).encode('utf-8'))
                if res.status_code != 200:
                    self.log.error('Failed to post request to search order get error=%s', res.text)
                    raise RakutenAPIError('Failed to post request to search order get status not 200')
            except Exception:
                self.log.exception('Failed to post request to get order')
                raise RakutenAPIError('Failed to post request to get order')

            res_json = res.json()
            for order_model in res_json.get('OrderModelList', []):
                order_number = order_model['orderNumber']
                order_progress = order_model['orderProgress']

                order_items = []
                for package_model in order_model['PackageModelList']:
                    for item_model in package_model['ItemModelList']:
                        item_name = item_model['itemName']
                        manage_number = item_model['manageNumber']
                        order_items.append(OrderItemData(item_name=item_name, manage_number=manage_number))

                orders.append(OrderData(order_number=order_number,
                                        order_progress=order_progress,
                                        order_items=order_items))

        return orders


class RakutenInventoryAPI:
    def __init__(self, log: Logger):
        self.log = log
        self._client = zeep.Client(wsdl=const.RMS_WSDL_FILE)

    def get(self, item_urls: List[str], chunk_size: int = 1000):
        # リストを分割
        item_urls_n = [item_urls[i:i + chunk_size] for i in range(0, len(item_urls), chunk_size)]

        external_user_auth_model = self._client.get_type('ns1:ExternalUserAuthModel')(
            authKey=RakutenAPI.get_authz(),
            userName="フクワウチ",
            shopUrl="page-to-sell-a-used",
        )

        factory = self._client.type_factory('ns1')
        array_of_string = self._client.get_type('ns0:ArrayOfString')

        inventories = []
        for item_urls_1 in item_urls_n:
            try:
                response = self._client.service.getInventoryExternal(
                    externalUserAuthModel=external_user_auth_model,
                    getRequestExternalModel=factory.GetRequestExternalModel(
                        itemUrl=array_of_string(item_urls_1)))
                # N00-000:正常終了 W00-201:商品エラーがあります E00-202:商品データがありません
                if response.errCode != 'N00-000':
                    continue
            except Exception:
                self.log.exception('Failed to get inventory')
                raise RakutenAPIError('Failed to get inventory')

            get_external_item_array = getattr(response, 'getResponseExternalItem', None)
            get_external_item = getattr(get_external_item_array, 'GetResponseExternalItem', None)
            if not get_external_item:
                continue

            for item in get_external_item:
                item_url = item.itemUrl

                get_item_detail_array = getattr(item, 'getResponseExternalItemDetail', None)
                get_external_item_detail = getattr(get_item_detail_array, 'GetResponseExternalItemDetail', None)
                if get_external_item_detail:
                    for item_detail in get_external_item_detail:
                        inventory_count = item_detail.inventoryCount
                        inventories.append(InventoryData(item_url=item_url, inventory_count=inventory_count))

        return inventories

    def update(self, update_items: List[InventoryUpdateData]) -> List[InventoryUpdateErrorResponseItemData]:
        _xsd_types = _xsd_types = dict(((t.name, t) for t in self._client.wsdl.types.types))
        update_request_external_item = _xsd_types['UpdateRequestExternalItem']

        update_request_items = []
        for item in update_items:
            update_request = update_request_external_item(
                itemUrl=item.item_url,
                inventoryType=2,
                restTypeFlag=0,
                HChoiceName=None,
                VChoiceName=None,
                orderFlag=0,
                nokoriThreshold=0,
                inventoryUpdateMode=1,
                inventory=item.inventory_count,
                inventoryBackFlag=0,
                normalDeliveryDeleteFlag=False,
                normalDeliveryId=0,
                lackDeliveryDeleteFlag=False,
                lackDeliveryId=0,
                orderSalesFlag=0
            )
            update_request_items.append(update_request)

        factory = self._client.type_factory('ns1')
        external_user_auth_model = self._client.get_type('ns1:ExternalUserAuthModel')(
            authKey=RakutenAPI.get_authz(),
            userName="フクワウチ",
            shopUrl="page-to-sell-a-used",
        )
        try:
            response = self._client.service.updateInventoryExternal(
                externalUserAuthModel=external_user_auth_model,
                updateRequestExternalModel=factory.UpdateRequestExternalModel(
                    factory.ArrayOfUpdateRequestExternalItem(update_request_items)))
        except Exception:
            self.log.exception('Failed to update inventory')
            raise RakutenAPIError('Failed to update inventory')

        # N00-000:正常終了
        if response.errCode == 'N00-000':
            return []

        update_response_external_model = getattr(response, 'updateResponseExternalItem', None)
        update_response_external_item = getattr(update_response_external_model, 'UpdateResponseExternalItem', None)
        if not update_response_external_item:
            return []

        error_items = []
        for item in update_response_external_item:
            error_items.append(
                InventoryUpdateErrorResponseItemData(item_url=item.itemUrl,
                                                     error_code=item.itemErrCode,
                                                     error_message=item.itemErrMessage))

        return error_items
