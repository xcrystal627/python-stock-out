# -*- coding: utf-8 -*-

import functools
import json
from typing import Optional, Dict, List
import pika
from pika.adapters.blocking_connection import BlockingChannel
from dataclasses import dataclass

import const


@dataclass
class MQMsgData:
    id: str
    item_ids: List[str]
    msg_send_time: str


class MQError(Exception):
    pretext = ''

    def __init__(self, message, *args):
        if self.pretext:
            message = f"{self.pretext}: {message}"
        super().__init__(message, *args)


class MQ:
    def __init__(self,
                 host: str,
                 vhost: str,
                 username: str,
                 password: str,
                 exchange: str,
                 queue: str,
                 routing_key: str,
                 exchange_type: str = const.MQ_EXCHANGE_TYPE,
                 passive: bool = const.MQ_PASSIVE,
                 durable: bool = const.MQ_DURABLE,
                 connection_attempts: int = const.MQ_CONNECTION_ATTEMPTS
                 ):
        self.host = host
        self.vhost = vhost
        self.username = username
        self.password = password
        self.exchange = exchange
        self.queue = queue
        self.routing_key = routing_key
        self.exchange_type = exchange_type
        self.passive = passive
        self.durable = durable
        self.connection_attempts = connection_attempts

        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None

    def __del__(self):
        self.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def open(self):
        if self.is_open():
            return

        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.host,
                    virtual_host=self.vhost,
                    credentials=pika.PlainCredentials(username=self.username, password=self.password),
                    connection_attempts=self.connection_attempts,
                ),
            )
        except Exception:
            raise MQError('Queue Connection AMQPError')

        try:
            channel = connection.channel()
        except Exception:
            if connection:
                if connection.is_open:
                    connection.close()
            raise MQError('Message queue AMQPError when connection.channel()')

        try:
            channel.exchange_declare(
                exchange=self.exchange,
                exchange_type=self.exchange_type,
                passive=self.passive,
                durable=self.durable,
                auto_delete=const.MQ_EXCHANGE_AUTO_DELETE,
            )
            channel.queue_declare(
                queue=self.queue,
                passive=self.passive,
                durable=self.durable,
                exclusive=const.MQ_QUEUE_EXCLUSIVE,
                auto_delete=const.MQ_QUEUE_AUTO_DELETE,
            )
            channel.queue_bind(
                exchange=self.exchange,
                queue=self.queue,
                routing_key=self.routing_key
            )
            channel.basic_qos(prefetch_count=const.MQ_QOS_PRE_FETCH_COUNT)
        except Exception:
            if channel:
                if channel.is_open:
                    channel.close()
            if connection:
                if connection.is_open:
                    connection.close()
            raise MQError('Declare and bind AMQPError')

        self.connection = connection
        self.channel = channel

    def close(self):
        try:
            if self.channel:
                if self.channel.is_open:
                    self.channel.stop_consuming()
                    self.channel.close()
            if self.connection:
                if self.connection.is_open:
                    self.connection.close()
        except Exception:
            pass
        self.channel = None
        self.connection = None

    def is_open(self):
        if self.connection and self.channel:
            if self.connection.is_open and self.channel.is_open:
                return True
        return False

    def send_message(self, message: Dict):
        if not self.is_open():
            raise MQError('Cannot open connect')

        try:
            message_json = json.dumps(message, ensure_ascii=False)
        except Exception:
            raise MQError('JSON dump exception error')

        try:
            self.channel.basic_publish(
                exchange=self.exchange,
                routing_key=self.routing_key,
                body=message_json.encode('utf-8'),
                properties=pika.BasicProperties(
                    delivery_mode=const.MQ_DELIVERY_MODE,
                    content_type='application/json',
                ))
        except Exception:
            raise MQError('Publish message AMQPError')

    def receive_message(self, callback: functools.partial):
        if not self.is_open():
            raise MQError('not open connect')

        try:
            on_message_callback = functools.partial(self._on_message, func=callback)
            self.channel.basic_consume(queue=self.queue,
                                       on_message_callback=on_message_callback)
            self.channel.start_consuming()
        except Exception:
            raise MQError('Receive message Exception Error')

    @staticmethod
    def _on_message(channel: BlockingChannel,
                    method: pika.spec.Basic.Deliver,
                    properties: pika.BasicProperties,  # noqa
                    body: bytes,
                    func: functools.partial):
        try:
            decoded_body = body.decode('utf-8')
            msg = json.loads(decoded_body)
        except Exception:
            # メッセージ異常
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            result = func(msg=msg)
            if result:
                channel.basic_ack(delivery_tag=method.delivery_tag)
            else:
                channel.basic_nack(delivery_tag=method.delivery_tag)
        except Exception:
            return
