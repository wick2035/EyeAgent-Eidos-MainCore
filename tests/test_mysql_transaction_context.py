import unittest

import pymysql

from infrastructure.database.mysql_connection import MySQLConnectionPool


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    def execute(self, sql, params=None):
        self.connection.statements.append((sql, params))
        if sql == "FAIL":
            raise RuntimeError("second write failed")
        if sql == "DEADLOCK":
            raise pymysql.err.OperationalError(1213, "deadlock found")
        return 1

    def executemany(self, sql, params_list):
        params = list(params_list)
        self.connection.statements.append((sql, params))
        if sql == "FAIL_MANY":
            raise RuntimeError("segment batch failed")
        return len(params)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.statements = []
        self.cursor_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0
        self.cursor_instance = None

    def cursor(self):
        self.cursor_calls += 1
        self.cursor_instance = FakeCursor(self)
        return self.cursor_instance

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.close_calls += 1


class FakePooledDB:
    def close(self):
        pass


class FakeMySQLConnectionPool(MySQLConnectionPool):
    def __init__(self, connection):
        self.fake_connection = connection
        self.connection_calls = 0
        super().__init__()

    def _init_pool(self):
        self._pool = FakePooledDB()

    def _get_connection(self):
        self.connection_calls += 1
        return self.fake_connection


class TinyRepository:
    def __init__(self, db):
        self.db = db

    def insert(self, value):
        self.db.execute("INSERT", (value,))


class MySQLTransactionContextTest(unittest.TestCase):
    def test_nested_repository_calls_reuse_one_connection(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)
        repository = TinyRepository(db)

        with db.transaction():
            repository.insert("first")
            with db.transaction():
                repository.insert("second")

        self.assertEqual(db.connection_calls, 1)
        self.assertEqual(connection.cursor_calls, 1)
        self.assertEqual(connection.commit_calls, 1)
        self.assertEqual(connection.rollback_calls, 0)
        self.assertEqual(connection.close_calls, 1)
        self.assertTrue(connection.cursor_instance.closed)

    def test_second_write_failure_rolls_back_both_writes(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)

        with self.assertRaisesRegex(RuntimeError, "second write failed"):
            with db.transaction():
                db.execute("INSERT", ("first",))
                db.execute("FAIL", ("second",))

        self.assertEqual(connection.statements, [
            ("INSERT", ("first",)),
            ("FAIL", ("second",)),
        ])
        self.assertEqual(connection.commit_calls, 0)
        self.assertEqual(connection.rollback_calls, 1)
        self.assertEqual(connection.close_calls, 1)

    def test_outermost_success_commits_once(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)

        with db.transaction():
            db.execute("INSERT", ("only",))

        self.assertEqual(connection.commit_calls, 1)
        self.assertEqual(connection.rollback_calls, 0)

    def test_deadlock_inside_transaction_is_not_retried_per_statement(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)

        with self.assertRaises(pymysql.err.OperationalError) as raised:
            with db.transaction():
                db.execute("INSERT", ("first",))
                db.execute("DEADLOCK", ("second",))

        self.assertEqual(raised.exception.args[0], 1213)
        self.assertEqual(connection.statements, [
            ("INSERT", ("first",)),
            ("DEADLOCK", ("second",)),
        ])
        self.assertEqual(connection.commit_calls, 0)
        self.assertEqual(connection.rollback_calls, 1)

    def test_batch_write_reuses_transaction_and_commits_with_state_update(self):
        connection = FakeConnection()
        db = FakeMySQLConnectionPool(connection)

        with db.transaction():
            db.execute_many("INSERT_SEGMENTS", [("segment-1",), ("segment-2",)])
            db.execute("MARK_READY", ("ingestion-1", 2))

        self.assertEqual(connection.statements, [
            ("INSERT_SEGMENTS", [("segment-1",), ("segment-2",)]),
            ("MARK_READY", ("ingestion-1", 2)),
        ])
        self.assertEqual(db.connection_calls, 1)
        self.assertEqual(connection.commit_calls, 1)
        self.assertEqual(connection.rollback_calls, 0)


if __name__ == "__main__":
    unittest.main()
