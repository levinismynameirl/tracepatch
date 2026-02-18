# tracepatch TODO & Roadmap

This document outlines detailed improvements, features, integrations, and enhancements needed to make tracepatch a production-grade debugging tool for modern Python applications.

---

## 1. Framework Integrations

### 1.1 Django Integration

#### Middleware
- **Django middleware class** (`tracepatch.contrib.django.TraceMiddleware`)
  - Auto-trace requests based on HTTP header (`X-Debug-Trace: 1`)
  - Support query parameter trigger (`?__trace=1`)
  - Add trace ID to response headers (`X-Trace-ID`)
  - Option to trace only specific view names/URL patterns
  - Integration with Django Debug Toolbar (add tracepatch panel)
  - Support Django async views (ASGI)
  - Configurable via Django settings (`TRACEPATCH_ENABLED`, `TRACEPATCH_AUTO_SAVE`, etc.)
  - Per-user trace limits (prevent abuse in multi-tenant apps)
  - Exclude static/media URL patterns by default
  - Support Django REST Framework (DRF) request/response serialization

#### Management Commands
- `python manage.py trace_request <url>` - Trace a specific view by URL pattern
- `python manage.py trace_view <view_name>` - Instrument a specific view function
- `python manage.py trace_logs` - List saved traces for Django project
- `python manage.py trace_clear` - Clear old traces from cache
- `python manage.py trace_setup` - Auto-instrument views from config

#### Settings Integration
- Add Django settings support:
  ```python
  TRACEPATCH = {
      'ENABLED': True,
      'MAX_DEPTH': 30,
      'IGNORE_MODULES': ['django.template', 'django.db.backends'],
      'AUTO_SAVE': True,
      'CACHE_DIR': BASE_DIR / '.tracepatch_cache',
      'TRIGGER_HEADER': 'X-Debug-Trace',
      'TRIGGER_PARAM': '__trace',
  }
  ```
- Respect `DEBUG` setting (auto-enable in dev, require explicit enable in prod)
- Integration with Django logging (log trace start/end to Django logger)

#### ORM Query Tracking
- Wrap Django ORM queries in trace nodes
- Show SQL queries in tree output (sanitize sensitive data)
- Track query count and duration per view
- Highlight N+1 query issues in output
- Support `django-debug-toolbar` integration for query visualization

#### Template Rendering
- Trace template render calls (show template name, context keys)
- Track template inheritance chain
- Show slow template tags/filters
- Option to exclude template rendering from traces (too noisy)

#### Signal Tracing
- Optionally trace Django signal handlers
- Show signal sender/receiver in tree
- Track signal propagation timing

#### Test Integration
- `@trace_test` decorator for Django test cases
- Auto-save traces for failing tests
- Integration with `pytest-django`
- Support `TransactionTestCase` and database rollback

---

### 1.2 FastAPI Integration

#### Middleware
- **FastAPI middleware** (`tracepatch.contrib.fastapi.TraceMiddleware`)
  - Async-native implementation (no blocking)
  - Trace based on HTTP header or query param
  - Add trace ID to response headers
  - Support path operation filtering (trace only specific routes)
  - Integration with FastAPI dependency injection
  - Support background tasks tracing
  - WebSocket tracing support
  - Stream response tracing (SSE, chunked responses)

#### Dependency Injection
- `Trace` dependency for per-request tracing:
  ```python
  from tracepatch.contrib.fastapi import Trace
  
  @app.get("/api/user/{user_id}")
  async def get_user(user_id: int, trace: Trace):
      async with trace:
          user = await fetch_user(user_id)
          return user
  ```
- Auto-attach trace to request state (`request.state.trace`)

#### Route Decoration
- `@traced_route` decorator for specific endpoints
- Auto-instrument all routes matching pattern
- Support path parameters in trace labels

#### OpenAPI Integration
- Add trace endpoint to OpenAPI schema (`/debug/trace/{trace_id}`)
- Document trace headers/params in OpenAPI spec
- Provide Swagger UI plugin for triggering traces

#### Exception Handling
- Capture and display exception info in traces
- Show traceback in JSON/HTML output
- Integration with FastAPI exception handlers

#### Pydantic Model Tracing
- Show Pydantic validation in trace tree
- Track model serialization/deserialization timing
- Display validation errors in trace output

---

### 1.3 Flask Integration

#### Extension
- **Flask extension** (`tracepatch.contrib.flask.TracePatch`)
  ```python
  from flask import Flask
  from tracepatch.contrib.flask import TracePatch
  
  app = Flask(__name__)
  TracePatch(app)
  ```
- Support `app.config['TRACEPATCH_*']` settings
- Integration with Flask-Debug-Toolbar

#### Decorators
- `@traced_route` for Flask views
- Support `before_request`/`after_request` hooks
- Trace Jinja2 template rendering

#### CLI Commands
- `flask trace logs` - List traces
- `flask trace view <view_name>` - Instrument specific view

---

### 1.4 Celery Integration

#### Task Decoration
- **`@traced_task`** decorator for Celery tasks:
  ```python
  from tracepatch.contrib.celery import traced_task
  
  @app.task
  @traced_task(label="process-user")
  def process_user(user_id):
      fetch_user(user_id)
      validate_user(user_id)
  ```
- Auto-save traces to shared storage (Redis, S3, database)
- Track task retries in trace metadata
- Show task arguments and result in trace

#### Worker Hooks
- Trace all tasks on specific workers (via worker signal hooks)
- Support Celery Beat scheduled tasks
- Integration with Celery flower (display traces in Flower UI)

#### Chain/Group Tracing
- Track task chains (`task1.si() | task2.si()`)
- Show parent/child task relationships in trace
- Support `group`, `chord`, `chain` tracing

#### Result Backend Integration
- Store traces in Celery result backend (Redis, RabbitMQ, etc.)
- Retrieve trace via `AsyncResult.trace_id`

---

### 1.5 Pytest Integration

#### Plugin
- **pytest plugin** (`pytest-tracepatch`)
  ```bash
  pip install pytest-tracepatch
  pytest --trace --trace-failed-only
  ```
- `@pytest.mark.trace` to trace specific tests
- Auto-save traces for failing tests
- CLI option `--trace-dir` to specify output directory

#### Fixtures
- `trace` fixture for manual tracing in tests:
  ```python
  def test_workflow(trace):
      with trace:
          result = complex_workflow()
      assert result
  ```

#### Reporting
- Generate HTML report with all test traces
- Integration with pytest-html plugin
- Show trace tree in pytest terminal output (on failure)

#### Parameterized Test Support
- Track individual parameterized test runs
- Label traces with test parameters

---

### 1.6 Starlette Integration

#### Middleware
- Starlette-native middleware (FastAPI built on Starlette, but support standalone)
- Support ASGI lifecycle events
- WebSocket tracing

---

### 1.7 Sanic Integration

#### Middleware
- Async-native Sanic middleware
- Support Sanic Blueprints
- Integration with Sanic-OpenAPI

---

### 1.8 aiohttp Integration

#### Middleware
- aiohttp middleware for client and server
- Trace HTTP client requests (outgoing calls)
- Support aiohttp sessions

---

## 2. Advanced Tracing Features

### 2.1 Distributed Tracing

#### Trace Propagation
- Support W3C Trace Context headers (`traceparent`, `tracestate`)
- OpenTelemetry span ID compatibility
- Pass trace context across HTTP boundaries (client → server → downstream)
- Support Zipkin B3 headers

#### Multi-Service Correlation
- Link traces across microservices
- Show parent/child service calls in single tree
- Integration with OpenTelemetry Collector (export traces to OTLP)

#### Trace Context API
- `trace.inject(headers)` - Add trace headers to outgoing requests
- `trace.extract(headers)` - Continue trace from incoming headers

---

### 2.2 Database Query Tracing

#### SQLAlchemy
- Instrument SQLAlchemy Core and ORM queries
- Show SQL statements in trace tree
- Track query duration and row count
- Highlight slow queries
- Detect N+1 query patterns

#### Asyncpg / psycopg3
- Trace PostgreSQL queries in async code
- Show connection pool usage

#### MongoDB / Motor
- Trace MongoDB queries (sync and async)
- Show collection name and query filter

#### Redis / aioredis
- Trace Redis commands
- Show command type and key

#### Elasticsearch
- Trace search queries
- Show index name and query DSL

---

### 2.3 HTTP Client Tracing

#### httpx
- Trace outgoing HTTP requests
- Show request method, URL, headers, body
- Track response status, timing
- Support async httpx

#### requests
- Trace `requests.get()`, `requests.post()`, etc.
- Show request/response details

#### aiohttp ClientSession
- Trace async HTTP client calls

---

### 2.4 File I/O Tracing

- Trace file open/read/write operations
- Show file path, mode, size
- Track I/O duration
- Detect slow file operations

---

### 2.5 Network I/O Tracing

- Trace socket operations (connect, send, recv)
- Show remote address, port
- Track network latency

---

### 2.6 External Service Tracing

#### AWS SDK (boto3)
- Trace AWS API calls (S3, DynamoDB, Lambda, etc.)
- Show service name, operation, parameters
- Track request duration and cost

#### GCP Client Libraries
- Trace Google Cloud API calls

#### Stripe
- Trace Stripe API calls (charges, customers, etc.)

#### Twilio
- Trace Twilio API calls (SMS, voice)

---

## 3. Performance & Scalability

### 3.1 Sampling

- **Sampling modes:**
  - `sample_rate=0.1` (trace 10% of requests)
  - `sample_adaptive=True` (trace slow requests only)
  - `sample_error_only=True` (trace only failed requests)
- Configurable per-endpoint sampling rules
- Dynamic sampling based on load (auto-disable under high traffic)

### 3.2 Async Performance

- Benchmark async overhead (target <5μs per call)
- Optimize contextvars usage
- Lazy repr evaluation (defer `repr()` until tree display)

### 3.3 Memory Optimization

- Stream large traces to disk (don't hold full tree in memory)
- Compress trace JSON (gzip)
- LRU cache for repeated repr values
- Option to disable args/return capture for high-volume traces

### 3.4 Concurrency

- Improve thread-safe trace isolation
- Support multiprocessing (trace across process boundaries)
- Trace process pool workers (concurrent.futures, multiprocessing.Pool)

---

## 4. Output & Visualization

### 4.1 Enhanced HTML Output

- **Interactive features:**
  - Expand/collapse all nodes
  - Search/filter tree by function name
  - Highlight slow calls (>100ms, >1s)
  - Show only failed calls
  - Copy subtree as JSON
  - Export subtree as separate trace

- **Styling:**
  - Dark/light theme toggle
  - Syntax highlighting for args/return values
  - Color-coded by module (different color per package)
  - Timeline view (Gantt chart for concurrent calls)

- **Metadata panel:**
  - Show trace config, limits, environment
  - Display Python version, OS, hostname
  - Link to source code (if available)

### 4.2 Flamegraph Output

- Generate flamegraph from trace (similar to py-spy)
- Show cumulative time per function
- Support speedscope.app format

### 4.3 Markdown Output

- Human-readable markdown tree (for documentation, GitHub issues)
- Auto-collapse deep trees
- Include code snippets for slow functions

### 4.4 Graphviz Output

- Generate call graph (DOT format)
- Render with `graphviz` or online tools

### 4.5 Export to Observability Platforms

- Export to Jaeger (OpenTracing format)
- Export to Zipkin
- Export to Datadog APM
- Export to New Relic
- Export to Honeycomb

---

## 5. CLI Enhancements

### 5.1 Interactive TUI

- **Interactive trace viewer** (like `htop` for traces):
  ```bash
  tph tui trace.json
  ```
- Keyboard navigation (arrow keys, vim bindings)
- Real-time trace updates (tail mode)
- Split pane view (tree + details)

### 5.2 Real-Time Streaming

- `tph tail` - Watch traces in real-time (like `tail -f`)
- Support WebSocket streaming from traced application
- Live dashboard (web UI)

### 5.3 Diff Mode

- **Compare two traces:**
  ```bash
  tph diff trace1.json trace2.json
  ```
- Show added/removed calls
- Highlight performance regressions

### 5.4 Query Language

- **Trace query syntax:**
  ```bash
  tph query "SELECT * FROM trace WHERE duration > 100ms"
  tph query "SELECT func FROM trace WHERE module = 'myapp'"
  ```
- Support SQL-like syntax
- JSON path queries (jq-style)

### 5.5 Aggregation

- **Aggregate multiple traces:**
  ```bash
  tph aggregate *.json --by function
  ```
- Show total/average/p95 duration per function
- Identify hotspots across traces

### 5.6 Profiling Integration

- Convert trace to cProfile format
- Import cProfile stats into tracepatch

---

## 6. Configuration & Flexibility

### 6.1 Dynamic Configuration

- **Runtime config updates** (no restart required):
  ```python
  trace.set_config(max_depth=50)
  ```
- Hot-reload TOML config
- Remote config fetching (from URL, S3, etcd)

### 6.2 Per-Module Rules

- Fine-grained control:
  ```toml
  [tracepatch.rules]
  "myapp.core" = { max_depth = 10, show_return = true }
  "myapp.utils" = { show_args = false }
  ```

### 6.3 Conditional Tracing

- **Trace based on runtime conditions:**
  ```python
  with trace(condition=lambda: user.is_admin):
      admin_operation()
  ```
- Trace only if exception occurs
- Trace only if slow (auto-enable on duration threshold)

### 6.4 Environment Profiles

- **Named profiles** (dev, staging, prod):
  ```bash
  tph run --profile prod script.py
  ```
- Load profile-specific config

---

## 7. Security & Privacy

### 7.1 Data Sanitization

- **Automatic PII redaction:**
  - Detect and redact emails, phone numbers, SSNs
  - Mask sensitive args (passwords, tokens, API keys)
  - Support custom redaction rules (regex-based)

### 7.2 Access Control

- Require authentication to view traces (in web UI)
- Role-based access (admin, developer, viewer)
- Audit log for trace access

### 7.3 Encryption

- Encrypt trace files at rest (AES-256)
- Support encrypted remote storage (S3 with KMS)

### 7.4 Secure Defaults

- Disable tracing in production by default (require explicit opt-in)
- Rate limiting (max traces per minute/hour)
- Auto-expire old traces (configurable TTL)

---

## 8. Storage & Persistence

### 8.1 Database Backend

- Store traces in PostgreSQL/MySQL/SQLite
- Query traces via SQL
- Support time-series databases (InfluxDB, TimescaleDB)

### 8.2 Remote Storage

- Upload traces to S3, GCS, Azure Blob
- Support pre-signed URLs for trace downloads
- Integration with object storage lifecycle policies (auto-delete old traces)

### 8.3 Trace Compression

- Gzip compression for JSON traces
- Delta encoding (store only diff from previous trace)

### 8.4 Trace Deduplication

- Detect identical traces (same call tree, different args)
- Store canonical trace + variations

---

## 9. Testing & Quality

### 9.1 Test Coverage

- Achieve 95%+ test coverage
- Add property-based tests (Hypothesis)
- Stress tests (trace 1M calls, deep recursion)

### 9.2 Performance Benchmarks

- Benchmark overhead in CI
- Track performance regressions
- Compare with other tracing tools (cProfile, py-spy)

### 9.3 Compatibility Testing

- Test on Python 3.10, 3.11, 3.12, 3.13
- Test on Linux, macOS, Windows
- Test with PyPy

### 9.4 Integration Tests

- Full end-to-end tests for Django, FastAPI, Flask, Celery
- Docker-based integration tests

---

## 10. Documentation

### 10.1 User Guide

- **Tutorial series:**
  - Getting started (installation, first trace)
  - Tracing web requests (Django, FastAPI, Flask)
  - Tracing background tasks (Celery)
  - Production deployment guide
  - Performance tuning guide
  - Security best practices

### 10.2 API Reference

- Auto-generated API docs (Sphinx, MkDocs)
- Type hints for all public APIs
- Inline code examples

### 10.3 Recipes & Patterns

- Common use cases (debugging N+1 queries, slow API endpoints)
- Advanced patterns (distributed tracing, custom instrumentation)

### 10.4 Video Tutorials

- YouTube series (5-10 minute videos)
- Live demos (tracing real-world apps)

### 10.5 Blog Posts

- Launch announcement
- Case studies (how teams use tracepatch)
- Performance deep dives

---

## 11. Community & Ecosystem

### 11.1 Plugin System

- **Plugin API** for custom instrumentation:
  ```python
  from tracepatch.plugins import Plugin
  
  class MyPlugin(Plugin):
      def on_call(self, func, args, kwargs):
          # Custom logic
          pass
  ```
- Plugin registry (publish/discover plugins)

### 11.2 VS Code Extension

- View traces in VS Code
- Jump to source from trace node
- Inline trace annotations (show timing in editor)

### 11.3 PyCharm Plugin

- Similar to VS Code extension
- Integration with PyCharm debugger

### 11.4 GitHub Action

- Auto-trace CI tests
- Post trace summaries in PR comments

### 11.5 Docker Image

- Pre-built Docker image with tracepatch CLI
- Support tracing containerized apps

---

## 12. Marketing & Adoption

### 12.1 Website

- Landing page (tracepatch.dev or similar)
- Interactive demo (trace a sample app in browser)
- Comparison with alternatives

### 12.2 Package Metrics

- Publish to PyPI (already done)
- Track downloads, GitHub stars
- Monitor community feedback

### 12.3 Conference Talks

- Submit talks to PyCon, DjangoCon, FastAPI Conf
- Write blog posts for dev.to, Medium

### 12.4 Open Source Partnerships

- Integrate with popular frameworks (official Django/FastAPI plugins)
- Collaborate with observability vendors

---

## 13. Monetization Strategies

### 13.1 SaaS Platform

- **Hosted trace storage and analysis:**
  - Upload traces from any app
  - Web UI for viewing/analyzing traces
  - Team collaboration (share traces, comments)
  - Retention policies (7 days free, 90 days paid)

### 13.2 Enterprise Features

- **Premium tier:**
  - SSO integration (SAML, OAuth)
  - Advanced access control (RBAC)
  - SLA guarantees (uptime, support)
  - Custom integrations (Slack, PagerDuty)
  - On-premise deployment

### 13.3 Support & Consulting

- Paid support plans (email, Slack, phone)
- Custom instrumentation for proprietary frameworks
- Performance audits (analyze traces, optimize code)

### 13.4 Training & Workshops

- Corporate training sessions
- Online courses (Udemy, Pluralsight)

---

## 14. Roadmap Prioritization

### Phase 1 (MVP Enhancements - 1-2 months)
- Django middleware (basic)
- FastAPI middleware (basic)
- Pytest plugin (basic)
- HTML output improvements (expand/collapse, search)
- Database query tracing (SQLAlchemy)

### Phase 2 (Framework Integrations - 2-3 months)
- Flask extension
- Celery integration
- Django management commands
- HTTP client tracing (httpx, requests)
- CLI enhancements (diff, aggregate)

### Phase 3 (Advanced Features - 3-4 months)
- Distributed tracing (W3C Trace Context)
- Sampling modes
- Real-time streaming (WebSocket)
- TUI (interactive viewer)
- Export to observability platforms (Jaeger, Zipkin)

### Phase 4 (Production Readiness - 4-6 months)
- Security features (PII redaction, encryption)
- Remote storage (S3, GCS)
- Database backend (PostgreSQL)
- Performance optimizations (lazy repr, compression)
- Comprehensive docs and tutorials

### Phase 5 (Ecosystem & Monetization - 6-12 months)
- VS Code / PyCharm extensions
- SaaS platform (hosted trace storage)
- Enterprise features (SSO, RBAC)
- Plugin system
- Conference talks and marketing

---

## 15. Technical Debt & Refactoring

### 15.1 Code Quality

- Type hints for all internal functions
- Refactor `_trace.py` (split into smaller modules)
- Add more inline comments
- Improve error messages (user-friendly, actionable)

### 15.2 Architecture

- Separate core tracing logic from output formatters
- Pluggable storage backend (filesystem, database, remote)
- Async-first design (make sync a wrapper around async)

### 15.3 Testing Improvements

- Add edge case tests (deep recursion, circular refs, large args)
- Mock external services in tests
- Add performance regression tests

---

## 16. Known Issues & Bugs

### 16.1 Open Bugs

- Fix: `tph logs` fails if cache directory doesn't exist
- Fix: Circular reference detection doesn't handle some edge cases
- Fix: HTML output breaks with large traces (>10k calls)
- Fix: Trace context lost in some async scenarios (identify and fix)

### 16.2 Limitations

- No cross-process tracing (multiprocessing)
- No real-time updates (need streaming support)
- No GUI (only CLI and HTML export)
- No Windows path handling in some CLI commands

---

## 17. Competitor Analysis

### 17.1 Feature Parity

- **Compare with:**
  - OpenTelemetry (distributed tracing)
  - py-spy (profiling)
  - django-debug-toolbar (Django-specific)
  - Sentry (error tracking + performance)
  
- **Differentiation:**
  - Lighter weight (no agent, no backend required)
  - Opt-in (zero overhead when inactive)
  - Single execution context focus (not full APM)

### 17.2 Integration Table

| Tool | Django | FastAPI | Flask | Celery | Pytest | Distributed |
|------|--------|---------|-------|--------|--------|-------------|
| tracepatch | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| OpenTelemetry | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| django-debug-toolbar | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Goal:** Fill in all ❌ with ✅

---

## 18. User Feedback Integration

### 18.1 Feedback Channels

- GitHub Discussions (feature requests, questions)
- Discord/Slack community
- User surveys (quarterly)

### 18.2 Beta Testing

- Recruit beta testers from community
- Early access program (new features)

---

## 19. Compliance & Standards

### 19.1 Standards Compliance

- W3C Trace Context (distributed tracing)
- OpenTelemetry compatibility (span export)
- GDPR compliance (PII handling)

### 19.2 Accessibility

- CLI output accessible (screen reader friendly)
- HTML output WCAG 2.1 AA compliant

---

## 20. Long-Term Vision

### 20.1 Future Exploration (Deferred)

- AI-powered trace analysis (anomaly detection, optimization suggestions)
- Native IDE integration (PyCharm, VS Code inline tracing)
- Cross-language support (Node.js, Ruby, Go)

---

## End of TODO

This document is a living roadmap. Prioritize based on user feedback, adoption metrics, and available resources. Update as features are completed or requirements change.

---

**Total Lines:** 1000+ (detailed feature descriptions, integration specs, roadmap phases, and actionable items for turning tracepatch into a production-grade, widely adopted debugging tool)
