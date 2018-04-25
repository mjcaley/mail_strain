#!/usr/bin/env python3

import asyncio
import logging
import sqlite3
from enum import Enum
from collections import namedtuple
from functools import partial


class AsyncCallable:
    def __init__(self, callback):
        self.callback = callback
        self.result = None
        self.done = asyncio.Event()


class Cursor:
    def __init__(self, connection, cursor):
        self._connection = connection
        self._cursor = cursor

    async def execute(self, sql, *parameters):
        callback = partial(self._cursor.execute, sql, *parameters)
        self._cursor = await self._connection._call(callback)

        return self

    async def executemany(self, sql, parameters):
        callback = partial(self._cursor.executemany, sql, parameters)
        self._cursor = await self._connection._call(callback)

        return self

    async def executescript(self, sql_script):
        callback = partial(self._cursor.executescript, sql_script)
        self._cursor = await self._connection._call(callback)

    async def fetchone(self):
        return await self._connection._call(self._cursor.fetchone)

    async def fetchmany(self, size=None):
        callback = partial(self._cursor.fetchmany, size or self._cursor.arraysize)
        return await self._connection._call(callback)

    async def fetchall(self):
        return await self._connection._call(self._cursor.fetchall)

    async def close(self):
        '''Close cursor.'''
        await self._connection._call(self._cursor.close)

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def arraysize(self):
        return self._cursor.arraysize

    @property
    def description(self):
        return self._cursor.description

    @property
    def connection(self):
        return self._connection


async def connect(database, timeout=None, detect_types=None, isolation_level=None, cached_statements=None, uri=None, loop=None):
    loop = loop or asyncio.get_event_loop()
    connection = Connection(database, loop)
    await connection.connect()

    return connection


class Connection:
    def __init__(self, database, loop: asyncio.AbstractEventLoop=None):
        self.database = database
        # self.timeout = timeout
        # self.detect_types = detect_types
        # self.isolation_level = isolation_level
        # self.cached_statements = cached_statements
        # self.uri = uri

        self._running = asyncio.Event()
        self._connection = None
        self._future = None
        self._queries = asyncio.Queue()
        self.loop = loop or asyncio.get_event_loop()

    def _loop(self):
        self._connection = sqlite3.connect(
            self.database,
            # timeout=self.timeout,
            # detect_types=self.detect_types,
            # isolation_level=self.isolation_level,
            # cached_statements=self.cached_statements,
            # uri=self.uri
        )

        self.loop.call_soon_threadsafe(self._running.set)

        while self.loop.call_soon_threadsafe(self._running.is_set) and self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._queries.get(), self.loop)
            try:
                query = future.result(timeout=0.1)
            except asyncio.TimeoutError:
                future.cancel()
                continue

            try:
                query.result = query.callback()
            except Exception as e:
                query.result = e
            finally:
                self.loop.call_soon_threadsafe(self._queries.task_done)
                self.loop.call_soon_threadsafe(query.done.set)
        self._connection.close()

    async def _call(self, callback):
        call = AsyncCallable(callback)
        await self._queries.put(call)
        await call.done.wait()
        if isinstance(call.result, Exception):
            raise call.result
        else:
            return call.result

    async def connect(self):
        if not self._running.is_set():
            self._future = self.loop.run_in_executor(None, self._loop)
        await self._running.wait()

    async def cursor(self):
        return Cursor(self, await self._call(self._connection.cursor))

    async def commit(self):
        await self._call(self._connection.commit)

    async def rollback(self):
        await self._call(self._connection.rollback)

    async def close(self):
        self._running.clear()
        await self._future
        self._connection = None
        self._future = None

    async def execute(self, sql, *parameters):
        cursor = await self.cursor()
        return await cursor.execute(sql, *parameters)

    async def executemany(self, sql, parameters):
        cursor = await self.cursor()
        return await cursor.executemany(sql, parameters)

    async def executescript(self, sql_script):
        cursor = await self.cursor()
        return await cursor.executescript(sql_script)

    async def create_function(self, name, num_params, func):
        raise NotImplementedError

    async def create_aggregate(self, name, num_params, func):
        raise NotImplementedError

    async def create_collation(self, name, callable):
        raise NotImplementedError

    async def set_authorizer(self, authorizer_callback):
        raise NotImplementedError


if __name__ == '__main__':
    async def main():
        conn = await connect(':memory:')
        cursor = await conn.cursor()
        thing_table = await cursor.execute('create table thing (a,b,c)')
        await cursor.execute('insert into thing values (1,2,3)')
        await cursor.execute('insert into thing values (1,2,3)')
        await cursor.execute('insert into thing values (1,2,3)')
        await cursor.execute('insert into thing values (1,2,3)')
        await cursor.execute('insert into thing values (1,2,3)')
        await cursor.execute('select * from thing')
        print(await thing_table.fetchall())
        await asyncio.sleep(3)
        # await conn.close()
        await asyncio.sleep(3)

    loop = asyncio.get_event_loop()
    # loop.set_debug(True)
    # logging.basicConfig(level=logging.DEBUG)
    loop.run_until_complete(main())
    print(loop.is_running())
    print('hey')


# DB_NAME = 'contortionist.db'
#
# Message = namedtuple('Message', ('id', 'message', 'status'))
#
#
# class MessageStatus(Enum):
#     NEW = 1
#     WORKING = 2
#     SENDING = 3
#     DONE = 4
#     ERROR = 5
#
#
# class JobStatus(Enum):
#     NEW = 1
#     WORKING = 2
#     DONE = 3
#     ERROR = 4
#
#
# class TaskStatus(Enum):
#     NEW = 1
#     WORKING = 2
#     DONE = 3
#     ERROR = 4
#
#
# class CommandType(Enum):
#     Query = 1
#     Stop = 99
#
#
# class Command:
#     def __init__(self, command_type, *args):
#         self.command_type = command_type
#         self.args = args
#         self.result = None
#         self.finished = asyncio.Event()
#
#     def finish(self, result):
#         self.result = result
#         self.finished.set()
#
# class Connection:
#     def __init__(self, filename, loop=None):
#         self.filename = filename
#         self._connected = False
#         self._queue = asyncio.Queue()
#         self._loop = loop or asyncio.get_event_loop()
#
#     def run(self):
#         self._connected = True
#         self._loop.run_in_executor(None, self._run)
#
#     def _run(self):
#         # Connect to sqlite
#         while True:
#             future_command = asyncio.run_coroutine_threadsafe(self._queue.get())
#             command = future_command.result()
#             if command.command_type == CommandType.Stop:
#                 return
#             elif command.command_type == CommandType.Query:
#                 pass
#                 # run sql query
#                 # call done(result)
#
#     def stop(self):
#         if self._connected:
#             asyncio.run_coroutine_threadsafe(self._queue.put(Command.Stop), self._loop)
#             self._connected = False
#
#
# class Database:
#     def __init__(self, filename):
#         self.filename = filename
#
#     async def create_message(self, message, status=MessageStatus.NEW):
#         async with aiosqlite.connect(self.filename) as db:
#             result = await db.execute('INSERT INTO messages (message, status) VALUES (?, ?)',
#                                       (message, status))
#             await db.commit()
#
#             return result.lastrowid
#
#     async def get_message(self, message_id):
#         async with aiosqlite.connect(self.filename) as db:
#             cursor = await db.execute('SELECT id, message, status FROM messages WHERE id=?', (message_id,))
#             results = await cursor.fetchone()
#             return Message(id=results[0], message=results[1], status=MessageStatus(results[2]))
#
#     # async def message_status(self, message_id):
#     #     async with aiosqlite.connect(self.filename) as db:
#     #         result = await db.execute('SELECT (status) FROM messages WHERE id=?', (message_id,))
#     #         return MessageStatus((await result.fetchone())[0])
#
#     async def set_message_status(self, message_id, status):
#         async with aiosqlite.connect(self.filename) as db:
#             await db.execute('UPDATE messages SET status = ? WHERE id = ?', (message_id, status.value))
#
#     async def create_job(self, message_id, status=JobStatus.NEW):
#         async with aiosqlite.connect(self.filename) as db:
#             result = await db.execute('INSERT INTO jobs (message_id, status) VALUES (?, ?)',
#                                       (message_id, status.value))
#             await db.commit()
#
#             return result.lastrowid
#
#     async def job_status(self, job_id):
#         async with aiosqlite.connect(self.filename) as db:
#             result = await db.execute('SELECT (status) FROM jobs WHERE id=?', (job_id,))
#             return JobStatus((await result.fetchone())[0])
#
#     async def create_task(self, job_id, name, priority, status=TaskStatus.NEW):
#         async with aiosqlite.connect(self.filename) as db:
#             result = await db.execute('INSERT INTO tasks (job_id, name, priority, status) VALUES (?, ?, ?, ?)',
#                                       (job_id, name, priority, status.value))
#             await db.commit()
#
#             return result.lastrowid
#
#     async def task_status(self, task_id):
#         async with aiosqlite.connect(self.filename) as db:
#             result = await db.execute('SELECT (status) FROM tasks WHERE id=?', (task_id,))
#             return TaskStatus((await result.fetchone())[0])
#
#
# class Column:
#     def __init__(self, native_type, primary_key=False):
#         self.native_type = native_type
#         self.primary_key = primary_key
#
# class String(Column):
#     def __init__(self):
#
#
# class Session:
#     pass
#
#
# class MessageORM:
#     def __init__(self):
#         self._id = None
#         self._message = None
#         self._status = None
#
#     @property
#     def id(self):
#         return self._id
#
#     @id.setter
#     def id(self, value):
#         self._id = value
#
#     @property
#     def message(self):
#         return self._message
#
#     @message.setter
#     def message(self, value):
#         self._message = value
#
#     @property
#     def status(self):
#         return self._status
#
#     @status.setter
#     def status(self, value):
#         self._status = value
