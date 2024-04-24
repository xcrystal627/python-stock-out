# -*- coding: utf-8 -*-
from typing import List
from dataclasses import dataclass
from datetime import datetime
import xml.etree.ElementTree as ET

import const
from logging import Logger
from apireq import APIRequests


@dataclass
class AuGetStockData:
    item_code: str
    stock_count: int


@dataclass
class AuUpdateStockData:
    item_code: str
    stock_count: int


@dataclass
class AuUpdateErrorResponseData:
    item_code: str
    error_code: str
    error_message: str


@dataclass
class AuGetTradeItemData:
    order_detail_id: int
    item_code: str
    item_name: str


@dataclass
class AuGetTradeData:
    order_id: int
    order_status: str
    details: List[AuGetTradeItemData]


class AuAPIBaseError(Exception):
    pretext = ''

    def __init__(self, message, *args):
        if self.pretext:
            message = f"{self.pretext}: {message}"
        super().__init__(message, *args)


class AuAPIError(Exception):
    pretext = 'AuPayマーケットAPIエラー'


class AuAPI:
    shop_id: int = const.AU_SHOP_ID
    base_url: str = 'https://api.manager.wowma.jp/wmshopapi'

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
        self.stock = AuStockAPI(api=self.api, log=log)
        self.trade = AuTradeAPI(api=self.api, log=log)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.api.close()

    @staticmethod
    def get_authz() -> bytes:
        auth = f'Bearer {const.AUPAYM_API_KEY}'
        return bytes(auth, encoding='utf-8')


class AuStockAPI:
    def __init__(self, api: APIRequests, log: Logger):
        self._api = api
        self.log = log

    def search(self, item_code: str, count_per_request: int = 500) -> List[AuGetStockData]:
        post_data = {
            'shopId': AuAPI.shop_id,
            'itemCode': item_code,
            'totalCount': count_per_request,
            'startCount': 1
        }

        headers = {
            'Authorization': AuAPI.get_authz(),
            'content-type': 'application/x-www-form-urlencoded',
        }
        try:
            url = AuAPI.base_url + '/searchStocks'
            response = self._api.request_get(url=url,
                                             headers=headers,
                                             payload=post_data)
            if response.status_code != 200:
                self.log.error('Failed to post request to stock search error=%s', response.text)
                raise AuAPIError('Failed to post request to stock search status not 200')
        except Exception:
            self.log.exception('Failed to post request to search stock')
            raise AuAPIError('Failed to post request to search stock')

        root = ET.fromstring(response.text)
        status = root.find('.//result/status').text
        if status != '0':
            return []

        stocks = []
        for result_stock in root.findall('.//searchResult/resultStocks'):
            item_code = result_stock.find('.//itemCode').text
            stock_count = int(result_stock.find('.//stockCount').text)
            stock_data = AuGetStockData(item_code=item_code,
                                        stock_count=stock_count)
            stocks.append(stock_data)

        return stocks

    def update(self, update_items: List[AuUpdateStockData]) -> List[AuUpdateErrorResponseData]:
        xml = f"""
        <request>
            <shopId>{AuAPI.shop_id}</shopId>
        </request>"""
        root = ET.fromstring(xml)
        root.set('version', '1.0')
        root.set('encoding', 'UTF-8')

        for item in update_items:
            xml = f"""
            <stockUpdateItem>
                <itemCode>{item.item_code}</itemCode>
                <stockSegment>1</stockSegment>
                <stockCount>{item.stock_count}</stockCount>
            </stockUpdateItem>"""
            el_stock_update_item = ET.fromstring(xml)
            root.append(el_stock_update_item)

        headers = {
            'Authorization': AuAPI.get_authz(),
            'content-type': 'application/xml; charset=utf-8',
        }
        url = AuAPI.base_url + '/updateStock'
        post_data = ET.tostring(element=root, encoding='utf-8', method='xml')
        try:
            response = self._api.request_post(url=url, headers=headers, data=post_data)
        except Exception:
            self.log.exception('Failed to post request to update stock')
            raise AuAPIError('Failed to post request to update stock')

        if not getattr(response, 'text', None):
            return []
        root = ET.fromstring(response.text)
        update_items = []
        for el_update_result in root.findall('.//updateResult'):
            if el_update_result.findall('.//itemCode'):
                item_code = el_update_result.find('.//itemCode').text

                if el_update_result.findall('.//error'):
                    error = el_update_result.find('.//error')
                    error_code = error.find('.//code').text
                    error_message = el_update_result.find('.//message').text
                    update_item = AuUpdateErrorResponseData(item_code=item_code,
                                                            error_code=error_code,
                                                            error_message=error_message)
                    update_items.append(update_item)

        return update_items


class AuTradeAPI:
    def __init__(self, api: APIRequests, log: Logger):
        self._api = api
        self.log = log

    def search(self,
               start_time: datetime,
               end_time: datetime,
               count_per_request: int = 1000) -> List[AuGetTradeData]:
        headers = {
            'Authorization': AuAPI.get_authz(),
            'content-type': 'application/x-www-form-urlencoded',
        }
        url = AuAPI.base_url + '//searchTradeInfoListProc'

        count = 1
        result_count = 1
        orders = []
        while count <= result_count:
            post_data = {
                'shopId': AuAPI.shop_id,
                'totalCount': count_per_request,
                'startCount': count,
                'dateType': 0,
                'startDate': start_time.strftime('%Y-%m-%d'),
                'endDate': end_time.strftime('%Y-%m-%d'),
            }
            try:
                response = self._api.request_get(url=url, headers=headers, payload=post_data)
                if response.status_code != 200:
                    self.log.error('Failed to post request to trade search error=%s', response.text)
                    raise AuAPIError('Failed to post request to trade search status not 200')
            except Exception:
                self.log.exception('Failed to get request to search trade')
                raise AuAPIError('Failed to get request to search trade')

            root = ET.fromstring(response.text)
            status = root.find('.//result/status').text
            if status != '0':
                continue

            result_count = int(root.find('.//resultCount').text)

            order_list = []
            for el_order_info in root.findall('.//orderInfo'):
                order_id = int(el_order_info.find('.//orderId').text)
                order_status = el_order_info.find('.//orderStatus').text

                details = []
                for el_detail in el_order_info.findall('.//detail'):
                    order_detail_id = int(el_detail.find('.//orderDetailId').text)
                    item_code = el_detail.find('.//itemCode').text
                    item_name = el_detail.find('.//itemName').text

                    detail_data = AuGetTradeItemData(order_detail_id=order_detail_id,
                                                     item_code=item_code,
                                                     item_name=item_name)
                    details.append(detail_data)

                    order_data = AuGetTradeData(order_id=order_id,
                                                order_status=order_status,
                                                details=details)
                    order_list.append(order_data)

            orders.extend(order_list)
            count += count_per_request

        return orders
