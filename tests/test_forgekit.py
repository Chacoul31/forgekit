import asyncio
import logging
import os
import tempfile
import threading
import unittest
from pathlib import Path

from forgekit import (
    Config,
    DiskCache,
    EventBus,
    Field,
    Pipeline,
    PipelineError,
    RateLimiter,
    Schema,
    Timer,
    ValidationError,
    async_map,
    atomic_write,
    camel_case,
    chunked,
    clamp,
    compose,
    deep_merge,
    dotted_get,
    dotted_set,
    first,
    flatten,
    gather_limit,
    get_logger,
    group_by,
    human_duration,
    human_size,
    kebab_case,
    normalize_whitespace,
    pascal_case,
    pipe,
    pmap,
    read_json,
    retry,
    slugify,
    snake_case,
    strip_accents,
    timed,
    truncate,
    ttl_cache,
    unique,
    write_json,
)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class RetryTests(unittest.TestCase):
    def test_succeeds_after_failures(self):
        calls = {"n": 0}

        @retry(attempts=3, delay=0, jitter=0)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("boom")
            return "ok"

        self.assertEqual(flaky(), "ok")
        self.assertEqual(calls["n"], 3)

    def test_exhausted_reraises_last_exception(self):
        @retry(attempts=2, delay=0, jitter=0)
        def always():
            raise ValueError("nope")

        with self.assertRaises(ValueError):
            always()

    def test_giveup_and_on_retry(self):
        seen = []
        calls = {"n": 0}

        @retry(attempts=5, delay=0, jitter=0, on_retry=lambda a, e: seen.append(a),
               giveup=lambda e: isinstance(e, KeyError))
        def f():
            calls["n"] += 1
            raise KeyError("x") if calls["n"] == 2 else RuntimeError("y")

        with self.assertRaises(KeyError):
            f()
        self.assertEqual(calls["n"], 2)
        self.assertEqual(seen, [1])

    def test_only_listed_exceptions_are_retried(self):
        calls = {"n": 0}

        @retry(attempts=3, delay=0, jitter=0, exceptions=(ConnectionError,))
        def f():
            calls["n"] += 1
            raise ValueError("pas réessayé")

        with self.assertRaises(ValueError):
            f()
        self.assertEqual(calls["n"], 1)

    def test_async(self):
        calls = {"n": 0}

        @retry(attempts=3, delay=0, jitter=0)
        async def f():
            calls["n"] += 1
            if calls["n"] < 2:
                raise OSError()
            return 42

        self.assertEqual(asyncio.run(f()), 42)
        self.assertEqual(calls["n"], 2)

    def test_invalid_attempts(self):
        with self.assertRaises(ValueError):
            retry(attempts=0)


class CacheTests(unittest.TestCase):
    def test_ttl_expiry(self):
        clock = FakeClock()
        calls = []

        @ttl_cache(ttl=10, clock=clock)
        def f(x):
            calls.append(x)
            return x * 2

        self.assertEqual(f(2), 4)
        self.assertEqual(f(2), 4)
        self.assertEqual(len(calls), 1)
        clock.t = 11
        f(2)
        self.assertEqual(len(calls), 2)

    def test_lru_eviction_and_info(self):
        calls = []

        @ttl_cache(maxsize=2)
        def f(x):
            calls.append(x)
            return x

        f(1); f(2); f(1); f(3)  # 2 est évincé
        f(2)
        self.assertEqual(calls, [1, 2, 3, 2])
        info = f.cache_info()
        self.assertEqual(info.hits, 1)
        self.assertEqual(info.maxsize, 2)
        f.cache_clear()
        self.assertEqual(f.cache_info().size, 0)

    def test_unhashable_args_and_invalidate(self):
        calls = []

        @ttl_cache
        def total(items):
            calls.append(1)
            return sum(items)

        self.assertEqual(total([1, 2, 3]), 6)
        self.assertEqual(total([1, 2, 3]), 6)
        self.assertEqual(len(calls), 1)
        total.cache_invalidate([1, 2, 3])
        total([1, 2, 3])
        self.assertEqual(len(calls), 2)

    def test_async_cache(self):
        calls = []

        @ttl_cache(ttl=100)
        async def f(x):
            calls.append(x)
            return x + 1

        async def run():
            return await f(1), await f(1)

        self.assertEqual(asyncio.run(run()), (2, 2))
        self.assertEqual(len(calls), 1)

    def test_disk_cache(self):
        with tempfile.TemporaryDirectory() as d:
            clock = FakeClock()
            cache = DiskCache(Path(d) / "c.db", clock=clock)
            cache.set("a", {"x": 1}, ttl=5)
            cache.set("b", [1, 2])
            self.assertEqual(cache.get("a"), {"x": 1})
            self.assertIn("b", cache)
            self.assertEqual(len(cache), 2)
            clock.t = 6
            self.assertIsNone(cache.get("a"))
            self.assertEqual(cache.get("b"), [1, 2])
            cache.set("c", 1, ttl=1)
            clock.t = 10
            self.assertEqual(cache.purge_expired(), 1)
            cache.delete("b")
            self.assertEqual(len(cache), 0)

    def test_disk_memoize(self):
        with tempfile.TemporaryDirectory() as d:
            cache = DiskCache(Path(d) / "m.db")
            calls = []

            @cache.memoize()
            def f(x):
                calls.append(x)
                return x * 3

            self.assertEqual(f(2), 6)
            self.assertEqual(f(2), 6)
            self.assertEqual(len(calls), 1)


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.sleeps = []

        def fake_sleep(s):
            self.sleeps.append(s)
            self.clock.t += s

        self.rl = RateLimiter(rate=2, per=1.0, clock=self.clock, sleep=fake_sleep)

    def test_burst_then_wait(self):
        self.rl.acquire()
        self.rl.acquire()
        self.assertEqual(self.sleeps, [])
        self.rl.acquire()
        self.assertEqual(len(self.sleeps), 1)
        self.assertAlmostEqual(self.sleeps[0], 0.5)

    def test_try_acquire(self):
        self.assertTrue(self.rl.try_acquire())
        self.assertTrue(self.rl.try_acquire())
        self.assertFalse(self.rl.try_acquire())
        self.clock.t += 0.5
        self.assertTrue(self.rl.try_acquire())

    def test_decorator_and_context(self):
        @self.rl
        def f():
            return 1

        self.assertEqual(f(), 1)
        with self.rl:
            pass

    def test_too_many_tokens(self):
        with self.assertRaises(ValueError):
            self.rl.acquire(5)

    def test_invalid_rate(self):
        with self.assertRaises(ValueError):
            RateLimiter(rate=0)


class TimingTests(unittest.TestCase):
    def test_timer_with_fake_clock(self):
        clock = FakeClock()
        t = Timer("x", clock=clock)
        with t:
            clock.t = 2.0
            self.assertEqual(t.lap(), 2.0)
            clock.t = 5.0
        self.assertEqual(t.elapsed, 5.0)
        self.assertEqual(t.laps, [2.0])
        self.assertEqual(str(t), "x: 5.0 s")

    def test_timer_not_started(self):
        with self.assertRaises(RuntimeError):
            Timer().stop()

    def test_timed_decorator(self):
        @timed
        def f():
            return 7

        self.assertEqual(f(), 7)
        f()
        self.assertEqual(f.calls, 2)
        self.assertGreaterEqual(f.total_time, 0)

    def test_timed_async(self):
        @timed(name="a")
        async def f():
            return 1

        self.assertEqual(asyncio.run(f()), 1)
        self.assertEqual(f.calls, 1)

    def test_timer_logs(self):
        records = []

        class Handler(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        log = logging.getLogger("test.timer")
        log.setLevel(logging.INFO)
        log.addHandler(Handler())
        with Timer("job", logger=log):
            pass
        self.assertTrue(records and records[0].startswith("job: "))


class ConfigTests(unittest.TestCase):
    def test_get_set_and_attr(self):
        cfg = Config({"db": {"host": "localhost", "port": "5432"}, "debug": "oui"})
        self.assertEqual(cfg.get("db.host"), "localhost")
        self.assertEqual(cfg.get("db.port", cast=int), 5432)
        self.assertIs(cfg.get("debug", cast=bool), True)
        self.assertEqual(cfg.get("absent", 3), 3)
        self.assertEqual(cfg.db.host, "localhost")
        self.assertIn("db.port", cfg)
        self.assertNotIn("db.nope", cfg)
        cfg.set("a.b.c", 1)
        self.assertEqual(cfg["a.b.c"], 1)

    def test_require(self):
        with self.assertRaises(KeyError):
            Config({}).require("x")

    def test_bad_bool(self):
        with self.assertRaises(ValueError):
            Config({"a": "peut-être"}).get("a", cast=bool)

    def test_merge_does_not_mutate(self):
        a = Config({"x": {"y": 1, "z": 2}})
        b = a.merge({"x": {"y": 9}, "w": 0})
        self.assertEqual(a.get("x.y"), 1)
        self.assertEqual(b.to_dict(), {"x": {"y": 9, "z": 2}, "w": 0})

    def test_from_env(self):
        env = {"APP_DB__HOST": "h", "APP_DB__PORT": "5432", "APP_DEBUG": "true", "OTHER": "x"}
        cfg = Config.from_env("APP", environ=env)
        self.assertEqual(cfg.to_dict(), {"db": {"host": "h", "port": 5432}, "debug": True})

    def test_from_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "c.json").write_text('{"a": {"b": 1}}', encoding="utf-8")
            (p / "c.toml").write_text('[a]\nb = 2\n', encoding="utf-8")
            (p / ".env").write_text(
                '# commentaire\nexport NAME="Awa"\nPORT=8080 # port\nDB__HOST=localhost\n', encoding="utf-8"
            )
            self.assertEqual(Config.from_file(p / "c.json").get("a.b"), 1)
            self.assertEqual(Config.from_file(p / "c.toml").get("a.b"), 2)
            env = Config.from_dotenv(p / ".env")
            self.assertEqual(env.get("name"), "Awa")
            self.assertEqual(env.get("port"), 8080)
            self.assertEqual(env.get("db.host"), "localhost")
            with self.assertRaises(ValueError):
                (p / "c.txt").write_text("x")
                Config.from_file(p / "c.txt")


class PipelineTests(unittest.TestCase):
    def test_basic_and_map(self):
        p = Pipeline(str.strip).then(str.lower) | (lambda s: s.replace("  ", " "))
        self.assertEqual(p("  Bonjour  MONDE "), "bonjour monde")
        self.assertEqual(list(p.map(["A ", " B"])), ["a", "b"])
        self.assertEqual(len(p), 3)

    def test_immutability(self):
        base = Pipeline(str.strip)
        base.then(str.upper)
        self.assertEqual(len(base), 1)

    def test_error_wrapping(self):
        p = Pipeline(int, lambda x: 1 / x, name="calc")
        with self.assertRaises(PipelineError) as ctx:
            p("0")
        self.assertEqual(ctx.exception.index, 1)
        self.assertIsInstance(ctx.exception.original, ZeroDivisionError)

    def test_on_error_recovers(self):
        p = Pipeline(int, lambda x: x + 1, on_error=lambda err, v: 0)
        self.assertEqual(p("abc"), 1)

    def test_compose_pipe(self):
        add1 = lambda x: x + 1
        double = lambda x: x * 2
        self.assertEqual(compose(add1, double)(5), 11)
        self.assertEqual(pipe(5, add1, double), 12)


def _boom_on_three(x):
    if x == 3:
        raise ValueError("trois")
    return x * 10


class ParallelTests(unittest.TestCase):
    def test_pmap_ordered(self):
        self.assertEqual(pmap(lambda x: x * 2, range(20), workers=4), [x * 2 for x in range(20)])

    def test_pmap_empty(self):
        self.assertEqual(pmap(abs, []), [])

    def test_pmap_raise(self):
        with self.assertRaises(ValueError):
            pmap(_boom_on_three, range(6), workers=2)

    def test_pmap_collect_and_skip(self):
        collected = pmap(_boom_on_three, range(5), on_error="collect")
        self.assertEqual(collected[:3], [0, 10, 20])
        self.assertIsInstance(collected[3], ValueError)
        self.assertEqual(pmap(_boom_on_three, range(5), on_error="skip"), [0, 10, 20, 40])

    def test_pmap_progress(self):
        seen = []
        pmap(abs, [-1, -2, -3], progress=lambda d, t: seen.append((d, t)))
        self.assertEqual(seen[-1], (3, 3))

    def test_pmap_process(self):
        self.assertEqual(pmap(abs, [-1, -2, -3], backend="process", workers=2), [1, 2, 3])

    def test_pmap_invalid_args(self):
        with self.assertRaises(ValueError):
            pmap(abs, [1], backend="gpu")
        with self.assertRaises(ValueError):
            pmap(abs, [1], on_error="ignore")

    def test_gather_limit_respects_limit(self):
        state = {"running": 0, "peak": 0}

        async def work(x):
            state["running"] += 1
            state["peak"] = max(state["peak"], state["running"])
            await asyncio.sleep(0.01)
            state["running"] -= 1
            return x

        result = asyncio.run(async_map(work, range(12), limit=3))
        self.assertEqual(result, list(range(12)))
        self.assertLessEqual(state["peak"], 3)

    def test_gather_limit_exceptions(self):
        async def ok():
            return 1

        async def bad():
            raise RuntimeError("x")

        res = asyncio.run(gather_limit([ok(), bad()], limit=2, return_exceptions=True))
        self.assertEqual(res[0], 1)
        self.assertIsInstance(res[1], RuntimeError)


class EventTests(unittest.TestCase):
    def test_on_emit_off(self):
        bus = EventBus()
        got = []
        handler = bus.on("e", lambda x: got.append(x))
        bus.emit("e", 1)
        bus.off("e", handler)
        bus.emit("e", 2)
        self.assertEqual(got, [1])

    def test_decorator_wildcard_once(self):
        bus = EventBus()
        log = []

        @bus.on("a")
        def h(v):
            log.append(("a", v))

        bus.on("*", lambda ev, *a, **k: log.append(("*", ev)))
        bus.once("a", lambda v: log.append(("once", v)))
        bus.emit("a", 1)
        bus.emit("a", 2)
        self.assertEqual(log.count(("once", 1)), 1)
        self.assertNotIn(("once", 2), log)
        self.assertIn(("*", "a"), log)
        self.assertEqual(bus.listeners("a"), 1)

    def test_error_isolation(self):
        bus = EventBus()
        got = []
        bus.on("e", lambda: 1 / 0)
        bus.on("e", lambda: got.append("ok"))
        with self.assertLogs("forgekit.events", level="ERROR"):
            bus.emit("e")
        self.assertEqual(got, ["ok"])

    def test_raise_errors(self):
        bus = EventBus(raise_errors=True)
        bus.on("e", lambda: 1 / 0)
        with self.assertLogs("forgekit.events", level="ERROR"):
            with self.assertRaises(ZeroDivisionError):
                bus.emit("e")

    def test_emit_async(self):
        bus = EventBus()

        async def h(x):
            return x + 1

        bus.on("e", h)
        bus.on("e", lambda x: x * 10)
        self.assertEqual(asyncio.run(bus.emit_async("e", 1)), [2, 10])

    def test_thread_safety(self):
        bus = EventBus()
        counter = []
        bus.on("e", lambda: counter.append(1))
        threads = [threading.Thread(target=lambda: [bus.emit("e") for _ in range(50)]) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(counter), 200)


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.schema = Schema({
            "nom": Field(str, min=2),
            "age": Field(int, min=0, max=150, coerce=True),
            "email": Field(str, pattern=r"[^@\s]+@[^@\s]+\.\w+"),
            "roles": Field(list, item=Field(str, choices=["admin", "user"]), default=list),
            "note": Field(str, required=False),
        })

    def test_valid_with_coercion_and_defaults(self):
        out = self.schema.validate({"nom": "Awa", "age": "21", "email": "awa@ex.ci"})
        self.assertEqual(out, {"nom": "Awa", "age": 21, "email": "awa@ex.ci", "roles": []})

    def test_collects_all_errors(self):
        with self.assertRaises(ValidationError) as ctx:
            self.schema.validate({"nom": "A", "age": 200, "roles": ["root"], "zzz": 1})
        errors = ctx.exception.errors
        self.assertEqual(set(errors), {"nom", "age", "email", "roles", "zzz"})
        self.assertIn("[0]", errors["roles"])
        self.assertEqual(errors["email"], "champ requis")
        self.assertEqual(errors["zzz"], "champ inconnu")

    def test_bool_is_not_int(self):
        self.assertFalse(Schema({"n": Field(int)}).is_valid({"n": True}))

    def test_int_accepted_as_float(self):
        self.assertEqual(Schema({"x": Field(float)}).validate({"x": 3}), {"x": 3.0})

    def test_nested_schema_paths(self):
        outer = Schema({"user": Field(Schema({"age": Field(int)}))})
        with self.assertRaises(ValidationError) as ctx:
            outer.validate({"user": {"age": "x"}})
        self.assertIn("user.age", ctx.exception.errors)

    def test_nullable_and_validator_and_extra(self):
        s = Schema({"a": Field(int, nullable=True), "b": Field(int, validator=lambda v: v % 2 == 0)}, allow_extra=True)
        self.assertEqual(s.validate({"a": None, "b": 4, "c": 1}), {"a": None, "b": 4, "c": 1})
        self.assertFalse(s.is_valid({"a": 1, "b": 3}))

    def test_not_a_dict(self):
        with self.assertRaises(ValidationError):
            self.schema.validate([1, 2])


class TextTests(unittest.TestCase):
    def test_accents_and_slug(self):
        self.assertEqual(strip_accents("Élève à Paris"), "Eleve a Paris")
        self.assertEqual(slugify("Réseaux & Télécoms 2026"), "reseaux-telecoms-2026")
        self.assertEqual(slugify("Un très long titre", max_length=6), "un-tre")
        self.assertEqual(slugify("a b", sep="_"), "a_b")

    def test_truncate(self):
        self.assertEqual(truncate("abc", 5), "abc")
        self.assertEqual(truncate("abcdefghij", 5), "abcd…")
        self.assertEqual(truncate("bonjour tout le monde", 12, whole_words=True), "bonjour…")
        self.assertEqual(truncate("bonjour tout le monde", 13, whole_words=True), "bonjour tout…")
        with self.assertRaises(ValueError):
            truncate("abc", 0, suffix="...")

    def test_whitespace_and_cases(self):
        self.assertEqual(normalize_whitespace("  a \n\t b  "), "a b")
        self.assertEqual(snake_case("HTTPServerError"), "http_server_error")
        self.assertEqual(snake_case("maVariable"), "ma_variable")
        self.assertEqual(camel_case("ma_variable-test"), "maVariableTest")
        self.assertEqual(pascal_case("ma variable"), "MaVariable")
        self.assertEqual(kebab_case("maVariable"), "ma-variable")

    def test_human_size(self):
        self.assertEqual(human_size(500), "500 o")
        self.assertEqual(human_size(1536), "1.5 Ko")
        self.assertEqual(human_size(5 * 1024 ** 3), "5.0 Go")

    def test_human_duration(self):
        self.assertEqual(human_duration(0.25), "250 ms")
        self.assertEqual(human_duration(42.5), "42.5 s")
        self.assertEqual(human_duration(3723), "1 h 2 min 3 s")
        self.assertEqual(human_duration(90061), "1 j 1 h 1 min 1 s")
        self.assertEqual(human_duration(60), "1 min")


class UtilsTests(unittest.TestCase):
    def test_chunked_flatten(self):
        self.assertEqual(list(chunked(range(5), 2)), [[0, 1], [2, 3], [4]])
        with self.assertRaises(ValueError):
            list(chunked([], 0))
        self.assertEqual(list(flatten([1, [2, [3, (4, 5)]], "ab"])), [1, 2, 3, 4, 5, "ab"])
        self.assertEqual(list(flatten([1, [2, [3]]], depth=1)), [1, 2, [3]])

    def test_deep_merge(self):
        a = {"x": {"y": 1}, "l": [1]}
        b = {"x": {"z": 2}, "l": [2]}
        merged = deep_merge(a, b)
        self.assertEqual(merged, {"x": {"y": 1, "z": 2}, "l": [2]})
        self.assertEqual(a, {"x": {"y": 1}, "l": [1]})

    def test_dotted(self):
        data = {"a": {"b": [{"c": 5}]}}
        self.assertEqual(dotted_get(data, "a.b.0.c"), 5)
        self.assertEqual(dotted_get(data, "a.b.9.c", "def"), "def")
        self.assertEqual(dotted_get(data, "a.x", "d"), "d")
        dotted_set(data, "n.m", 1)
        self.assertEqual(data["n"], {"m": 1})

    def test_group_unique_first_clamp(self):
        self.assertEqual(group_by(["a", "bb", "c"], len), {1: ["a", "c"], 2: ["bb"]})
        self.assertEqual(list(unique([3, 1, 3, 2, 1])), [3, 1, 2])
        self.assertEqual(list(unique([[1], [1], [2]])), [[1], [2]])
        self.assertEqual(list(unique(["A", "a", "b"], key=str.lower)), ["A", "b"])
        self.assertEqual(first([1, 2, 3], pred=lambda x: x > 1), 2)
        self.assertEqual(first([], default="vide"), "vide")
        self.assertEqual(clamp(15, 0, 10), 10)
        self.assertEqual(clamp(-1, 0, 10), 0)

    def test_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sous" / "f.json"
            write_json(p, {"nom": "Awa é"})
            self.assertEqual(read_json(p), {"nom": "Awa é"})
            self.assertEqual(read_json(Path(d) / "absent.json", default=[]), [])
            with self.assertRaises(FileNotFoundError):
                read_json(Path(d) / "absent.json")
            atomic_write(p.with_suffix(".bin"), b"\x00\x01", binary=True)
            self.assertEqual(p.with_suffix(".bin").read_bytes(), b"\x00\x01")
            self.assertEqual([f for f in os.listdir(p.parent) if f.endswith(".tmp")], [])


class LogTests(unittest.TestCase):
    def test_no_duplicate_handlers(self):
        import io

        buf = io.StringIO()
        get_logger("test.dup", stream=buf)
        log = get_logger("test.dup", stream=buf)
        log.info("une fois")
        self.assertEqual(buf.getvalue().count("une fois"), 1)

    def test_json_output(self):
        import io
        import json

        buf = io.StringIO()
        log = get_logger("test.json", json_output=True, stream=buf)
        log.warning("accentué é")
        record = json.loads(buf.getvalue().strip())
        self.assertEqual(record["level"], "WARNING")
        self.assertEqual(record["message"], "accentué é")

    def test_file_output(self):
        import io

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "a.log"
            log = get_logger("test.file", file=str(path), stream=io.StringIO())
            log.error("erreur")
            for h in log.handlers:
                h.flush()
            self.assertIn("erreur", path.read_text(encoding="utf-8"))
            get_logger("test.file", stream=io.StringIO())  # ferme le handler fichier


if __name__ == "__main__":
    unittest.main()
