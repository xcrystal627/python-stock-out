# -*- coding: utf-8 -*-

import os
import argparse
from datetime import datetime
from typing import Dict
import functools

import const
from logging import Logger
import logger
from mq import MQ, MQMsgData
import ysapi


def _stockout(msg_data: MQMsgData,
              task_no: int,
              log: Logger):
    if const.IS_PRODUCTION:
        profile_dirname = f'yshop_consumer_{task_no}'
    else:
        profile_dirname = f'yshop_consumer_test_{task_no}'
    profile_dir = os.path.join(const.CHROME_PROFILE_DIR, profile_dirname)

    if const.IS_PRODUCTION:
        auth_file = os.path.join(const.TMP_DIR, f'yshop_auth_consumer_{task_no}.json')
    else:
        auth_file = os.path.join(const.TMP_DIR, f'yshop_auth_consumer_test_{task_no}.json')

    with ysapi.YahooAPI(profile_dir=profile_dir,
                        log=log,
                        application_id=const.YJDN_APP_ID_CONSUMER,
                        secret=const.YJDN_SECRET_CONSUMER,
                        auth_file=auth_file,
                        business_id=const.YSHOP_BUSINESS_ID,
                        business_password=const.YSHOP_BUSINESS_ID,
                        yahoo_id=const.YSHOP_YAHOO_ID,
                        yahoo_password=const.YSHOP_YAHOO_PASSWORD) as api:
        try:
            log.info('Request to get stock item')
            stock_list = api.shopping.stock.get(item_codes=msg_data.item_ids)
        except Exception:
            log.exception('Failed to update stock')
            raise Exception('get stock error')

        set_list = []
        for stock_data in stock_list:
            log.info('Stock item data=%s', stock_data)
            item_id = stock_data.item_code
            quantity = stock_data.quantity
            if quantity > 0:
                log.info('Out of stock item id=%s', item_id)
                stock_data = ysapi.SetStockData(item_code=item_id, quantity=0)
                set_list.append(stock_data)

        if set_list:
            try:
                result = api.shopping.stock.set(set_stock_list=set_list)
                log.info('Updated stock items=%s', set_list)
                log.info('Not Updated stock items=%s', result)
                return
            except Exception:
                log.exception('Failed to update stock')
                raise Exception('stockout error')
        log.info('N/A update stock data')


def _relist_on_message(msg: Dict,
                       task_no: int,
                       log: Logger) -> bool:
    log.info('Message data=%s', logger.var_dump(msg))
    try:
        msg_data = MQMsgData(**msg)
    except Exception:
        raise Exception('Receive message parse error')
    log.info('Get queue message data=%s', msg_data)

    _stockout(msg_data=msg_data,
              task_no=task_no,
              log=log)
    return True


def _consumer(task_no: int, log: Logger):
    try:
        with MQ(**const.MQ_CONNECT,
                queue=const.MQ_YSHOP_QUEUE,
                routing_key=const.MQ_YSHOP_ROUTING_KEY) as queue:
            queue.open()
            callback = functools.partial(_relist_on_message,
                                         task_no=task_no,
                                         log=log)
            queue.receive_message(callback)

    except Exception:
        log.exception('Failed to MQ connect')
        raise


def main():
    parser = argparse.ArgumentParser(description='stockout_yshop_consumer')
    parser.add_argument('--task_no',
                        required=True,
                        type=int,
                        help='input process No type integer')

    arg_parser = parser.parse_args()
    log = logger.get_logger(task_name='stockout-yshop-consumer',
                            sub_name='main',
                            name_datetime=datetime.now(),
                            task_no=arg_parser.task_no,
                            **const.LOG_SETTING)
    log.info('Start task')
    log.info('Input args task_no=%s', arg_parser.task_no)

    _consumer(task_no=arg_parser.task_no, log=log)
    log.info('End task')


if __name__ == '__main__':
    main()
