# System Design — A Visual Learning Guide

A curated directory of system design learning resources, published by [SeeItFlow](https://seeitflow.com/). It organizes foundational topics, distributed systems building blocks and worked system design case studies into a learning path, and links each one to its full lesson on SeeItFlow, where the architecture is built up step by step with interactive visualizations.

It is written for students, early-career developers, experienced engineers and anyone preparing for a system design interview. This repository is the catalogue and navigation layer; the lessons, diagrams and case studies live on the website.

**Start here: [system design on SeeItFlow](https://seeitflow.com/system-design).**

## How to use this guide

If you are new to the subject, follow the [recommended learning sequence](#recommended-learning-sequence). If you already know the fundamentals, go straight to the [system design catalogue](#real-world-system-design-catalogue). Each entry names one idea or problem and links to the lesson that covers it in full; nothing here replaces the lesson itself.

## Table of contents

- [Recommended learning sequence](#recommended-learning-sequence)
- [Foundations and distributed building blocks](#foundations-and-distributed-building-blocks)
- [Real-world system design catalogue](#real-world-system-design-catalogue)
- [Architecture and production engineering](#architecture-and-production-engineering)
- [Using the guide for interviews](#using-the-guide-for-interviews)
- [About, contributing and license](#about-contributing-and-license)

## Recommended learning sequence

This is one reasonable order, not the only one. Skip phases you already know.

1. **Foundations.** Understand how requests travel across networks and how data is stored, indexed, cached and balanced across servers. Start with [Networking and APIs](#networking-and-apis), then [Data storage and indexing](#data-storage-and-indexing) and [Scalability and caching](#scalability-and-caching).
2. **Distributed systems.** Learn how messaging, replication, consistency and coordination behave when machines and networks fail. Continue with [Asynchronous communication](#asynchronous-communication), [Consistency and coordination](#consistency-and-coordination) and [Real-time delivery](#real-time-delivery).
3. **Apply and operate.** Work through complete designs in the [system design catalogue](#real-world-system-design-catalogue), then study the [resilience patterns](#resilience-patterns), [architecture trade-offs](#architecture-decisions-and-trade-offs) and [failure modes](#failure-modes-and-incident-analysis) that decide whether a design survives production.

## Foundations and distributed building blocks

<!-- BEGIN GENERATED:foundation -->
### Networking and APIs

- [HTTP](https://seeitflow.com/networking/foundations/http/fundamentals) — How HTTP methods, status codes, cookies and caching behave, and what changed between HTTP/1.1, HTTP/2 and HTTP/3.
- [DNS](https://seeitflow.com/networking/foundations/dns/fundamentals) — How a hostname is resolved through recursive lookups, and how record types, TTLs and caching affect failover and traffic distribution.
- [TCP](https://seeitflow.com/networking/foundations/tcp/fundamentals) — How a TCP connection is established, kept reliable under packet loss and congestion, and closed.
- [Load Balancer](https://seeitflow.com/networking/traffic-routing/loadbalancer/fundamentals) — How load balancers choose servers, detect unhealthy ones, drain connections and fail over between regions.
- [API Gateway](https://seeitflow.com/networking/traffic-routing/api-gateway/fundamentals) — What a single entry point adds to a service architecture: routing, authentication, rate limiting and aggregation.
- [Reverse Proxy (Nginx)](https://seeitflow.com/networking/traffic-routing/reverse-proxy/fundamentals) — What a reverse proxy such as Nginx does in front of servers: TLS termination, routing, caching and availability.
- [CDN](https://seeitflow.com/networking/advanced-networking/cdn/fundamentals) — How edge caches serve content close to users, and how TTLs, invalidation and origin shielding shape hit rates.
- [API Design](https://seeitflow.com/core-concepts/fundamentals/api-design) — How to design consistent API contracts, including resource modeling, error handling, pagination and versioning.
- [REST](https://seeitflow.com/core-concepts/fundamentals/rest) — Which constraints make an API RESTful, how method semantics interact with caching, and how REST differs from RPC.
- [gRPC](https://seeitflow.com/core-concepts/fundamentals/grpc) — How Protobuf contracts, streaming calls and deadlines work in gRPC, and when it is a better fit than REST.
- [Pagination](https://seeitflow.com/core-concepts/fundamentals/pagination) — Why offset pagination degrades on deep pages, how cursor and keyset pagination avoid it, and how changing data affects results.
- [Idempotency](https://seeitflow.com/core-concepts/fundamentals/idempotency) — How idempotency keys let clients retry safely, and how to handle concurrent duplicates and mismatched payloads.

### Data storage and indexing

- [Database Foundations](https://seeitflow.com/core-concepts/data-database-concepts/db-foundations) — How databases store data, run queries, guarantee durability and handle concurrent access before you study indexing or transactions.
- [Database Data Modeling](https://seeitflow.com/core-concepts/data-database-concepts/db-data-modeling) — How keys, constraints, normalization and query-driven design shape a schema, and how to migrate it without downtime.
- [Database Indexing](https://seeitflow.com/core-concepts/data-database-concepts/db-indexing) — How indexes speed up queries, how composite indexes are ordered, and why the optimizer sometimes ignores an index.
- [Database Transactions & Concurrency](https://seeitflow.com/core-concepts/data-database-concepts/db-transactions-concurrency) — What ACID guarantees, isolation levels, locking and MVCC mean, and when optimistic or pessimistic concurrency control fits.
- [Specialized Data Stores](https://seeitflow.com/core-concepts/data-database-concepts/db-specialized-data) — A comparison of relational, document, key-value, search, time-series, graph and vector databases, with guidance on matching each to a workload.
- [PostgreSQL](https://seeitflow.com/databases/technologies/postgres/fundamentals) — How PostgreSQL implements MVCC, indexing, query planning, write-ahead logging and streaming replication.
- [MongoDB](https://seeitflow.com/databases/technologies/mongodb/fundamentals) — How MongoDB handles flexible schemas, aggregation, multi-document transactions, replication and sharding.
- [Cassandra](https://seeitflow.com/databases/technologies/cassandra/fundamentals) — How Cassandra partitions and replicates data across a masterless cluster with tunable consistency, gossip and compaction.
- [Elasticsearch](https://seeitflow.com/databases/technologies/elasticsearch/fundamentals) — How inverted indexes, relevance scoring and sharding make near-real-time full-text search work across a cluster.

### Scalability and caching

- [Database Scaling](https://seeitflow.com/core-concepts/data-database-concepts/db-scaling) — The order in which to scale a database, from query tuning and caching to read replicas and sharding, and the failure modes of each step.
- [Redis](https://seeitflow.com/backend-systems/technologies/redis/fundamentals) — How Redis serves caching, sessions, streams and pub/sub from memory, and how persistence, replication and cluster sharding work.
- [Consistent Hashing](https://seeitflow.com/core-concepts/distributed-patterns/consistent-hashing) — How consistent hashing limits key movement when nodes join or leave, and which problems it does not solve.

### Asynchronous communication

- [Queues & Workers](https://seeitflow.com/core-concepts/async-systems/queues-workers) — How queues decouple submission from execution, what at-least-once and exactly-once delivery really promise, and how crashed workers recover.
- [Pub/Sub](https://seeitflow.com/core-concepts/async-systems/pub-sub) — How publish/subscribe fans events out to independent consumers, and how consumer groups, ordering scope and schema changes behave.
- [Job Processing](https://seeitflow.com/core-concepts/async-systems/job-processing) — How a background job moves through queued, running, retry and failed states, using leases, heartbeats and idempotency.
- [Outbox Pattern](https://seeitflow.com/core-concepts/async-systems/outbox-pattern) — Why writing to a database and publishing an event separately can lose one of them, how an outbox table closes that gap, and what delivery guarantee remains.
- [Dead-Letter Queues](https://seeitflow.com/core-concepts/async-systems/dead-letter-queues) — How dead-letter queues set aside unprocessable messages for inspection and replay, and why they do not replace a retry policy.
- [Kafka](https://seeitflow.com/backend-systems/technologies/kafka/fundamentals) — How Kafka partitions, replicates and retains events, and how consumer groups and offsets determine ordering and recovery.
- [RabbitMQ](https://seeitflow.com/backend-systems/technologies/rabbitmq/fundamentals) — How RabbitMQ routes messages through exchanges and queues, and how acknowledgements, flow control and durability handle failures.

### Consistency and coordination

- [Distributed Data](https://seeitflow.com/core-concepts/data-database-concepts/db-distributed-data) — How replication, partitioning, quorums and network partitions interact in distributed databases, and what CAP actually guarantees.
- [Distributed Locks](https://seeitflow.com/core-concepts/distributed-patterns/distributed-locks) — How leases, TTLs and fencing tokens make distributed locks safer, and when a lock is the wrong tool.
- [Saga Pattern](https://seeitflow.com/core-concepts/distributed-patterns/saga-pattern) — How sagas coordinate a multi-service transaction with compensating actions, and how orchestration, choreography and two-phase commit compare.
- [CQRS](https://seeitflow.com/core-concepts/distributed-patterns/cqrs) — Why separating command and query models can help, why it does not require event sourcing, and when it is worth the added complexity.
- [Event Sourcing](https://seeitflow.com/core-concepts/distributed-patterns/event-sourcing) — How state is derived from an immutable event history, and how snapshots and schema evolution work.
- [etcd](https://seeitflow.com/backend-systems/technologies/etcd/fundamentals) — How etcd uses Raft consensus, watches and leases to provide a strongly consistent store for coordination.

### Real-time delivery

- [Polling](https://seeitflow.com/core-concepts/realtime-systems/polling) — How interval polling trades freshness for simplicity, and how adaptive backoff and conditional requests help it scale.
- [Long Polling](https://seeitflow.com/core-concepts/realtime-systems/long-polling) — How holding a request open delivers updates sooner than polling, and how timeouts and reconnects shape the design.
- [Server-Sent Events](https://seeitflow.com/core-concepts/realtime-systems/sse) — How a server streams one-way updates to browsers over plain HTTP with Server-Sent Events, and how reconnection, Last-Event-ID, heartbeats and proxies interact.
- [WebSockets](https://seeitflow.com/core-concepts/realtime-systems/websockets) — How the WebSocket handshake, heartbeats, authentication and cross-server fan-out work for full-duplex messaging.
- [Presence](https://seeitflow.com/core-concepts/realtime-systems/presence) — How online status is inferred from heartbeats and TTLs, and why presence is approximate.

### AI system building blocks

- [LLM Overview](https://seeitflow.com/ai/llms/llm-overview) — How text flows through tokens, transformers and next-token generation, and which components and limits matter in LLM applications.
- [RAG Architecture](https://seeitflow.com/ai/rag/rag-overview) — How a retrieval-augmented generation pipeline moves from ingestion and chunking to retrieval, context assembly and citation checks.
- [Vector Databases](https://seeitflow.com/ai/rag/vector-databases) — How vector databases store embeddings and build approximate nearest-neighbor indexes with metadata filters, and when brute force is enough.
- [Model Serving](https://seeitflow.com/ai/ai-infrastructure/model-serving) — How LLM endpoints are deployed, routed, health-checked, autoscaled and monitored, including streaming responses and canary releases.

<!-- END GENERATED:foundation -->

## Real-world system design catalogue

These are learning designs inspired by familiar products. They are not company-authored case studies and do not describe any company's internal architecture. Each design on SeeItFlow is a five-page journey: the complete design with an embedded visual walkthrough, an architecture deep dive, trade-offs and decisions, failure and scale scenarios, and an interview perspective. The links below go to the complete design, which is the starting point for the rest.

<!-- BEGIN GENERATED:design -->
### Real-time communication and collaboration

| System design | Core engineering challenges |
| --- | --- |
| [Messaging Platform](https://seeitflow.com/system-design/foundations/whatsapp/complete-design) | persistent connections, message ordering, offline delivery, group fan-out |
| [Design Google Docs / Real-Time Collaborative Editor](https://seeitflow.com/system-design/intermediate/collab-editor/complete-design) | concurrent edits with operational transform, presence, offline sync, sharded document servers |
| [Notification System](https://seeitflow.com/system-design/foundations/notification/complete-design) | queue-based decoupling, priority lanes, retry storms, delivery tracking |
| [Real-Time Gaming Leaderboard](https://seeitflow.com/system-design/intermediate/leaderboard/complete-design) | sorted-set ranking, deterministic tie-breaking, idempotent score ingestion, season rollover |

### Booking, marketplaces and transactions

| System design | Core engineering challenges |
| --- | --- |
| [Ticket Booking System](https://seeitflow.com/system-design/intermediate/ticketbooking/complete-design) | double-booking races, temporary seat holds, hold expiry, admission control for high-demand events |
| [Hotel Reservation System](https://seeitflow.com/system-design/intermediate/hotel-reservation/complete-design) | room-night inventory, last-room races, atomic multi-night allocation, payment crash recovery |
| [Ride-Hailing Platform](https://seeitflow.com/system-design/advanced-distributed-systems/uber/complete-design) | geospatial indexing, rider-driver matching, ETA prediction, surge pricing |
| [E-commerce Platform](https://seeitflow.com/system-design/intermediate/ecommerce/complete-design) | inventory reservation, checkout orchestration, transactional outbox, asynchronous fulfillment |
| [Payment System](https://seeitflow.com/system-design/intermediate/payment/complete-design) | idempotency keys, timeout ambiguity, safe retries, provider reconciliation |
| [Splitwise (Shared Expense Manager)](https://seeitflow.com/system-design/intermediate/splitwise/complete-design) | split algorithms, immutable ledger, debt simplification, idempotent writes |
| [Stock Exchange](https://seeitflow.com/system-design/advanced-distributed-systems/stock-exchange/complete-design) | price-time priority matching, deterministic sequencing, durable journaling, fenced failover |

### Social, media and content delivery

| System design | Core engineering challenges |
| --- | --- |
| [Video Streaming Platform](https://seeitflow.com/system-design/intermediate/youtube/complete-design) | resumable uploads, asynchronous transcoding, adaptive bitrate streaming, CDN delivery |
| [Netflix](https://seeitflow.com/system-design/advanced-distributed-systems/netflix/complete-design) | control-plane and data-plane separation, asynchronous transcoding, adaptive bitrate delivery, regional resilience |
| [Social Media Platform](https://seeitflow.com/system-design/advanced-distributed-systems/instagram/complete-design) | media uploads, social graph, fan-out on write, the hot-user problem |
| [Twitter / X — Timeline](https://seeitflow.com/system-design/advanced-distributed-systems/twitter/complete-design) | fan-out on write, celebrity write amplification, hybrid fan-out, timeline caching |
| [File Storage & Sync](https://seeitflow.com/system-design/foundations/filestorage/complete-design) | resumable chunked uploads, separating metadata from file data, multi-device sync, conflict resolution |
| [Design a Global CDN](https://seeitflow.com/system-design/advanced-distributed-systems/cdn/complete-design) | edge caching, invalidation, origin shielding, anycast routing |

### Distributed infrastructure

| System design | Core engineering challenges |
| --- | --- |
| [URL Shortener](https://seeitflow.com/system-design/foundations/url-shortener/complete-design) | short-code generation, cache-first reads, redirect semantics, viral traffic spikes |
| [Distributed Task Scheduler](https://seeitflow.com/system-design/foundations/task-scheduler/complete-design) | due-job discovery, leader election, worker leases and heartbeats, retries with backoff |
| [Design a Distributed Cache](https://seeitflow.com/system-design/advanced-distributed-systems/distributed-cache/complete-design) | stampede protection, hot keys, sharding with consistent hashing or hash slots, replica failover |
| [Design a Distributed Key-Value Store](https://seeitflow.com/system-design/advanced-distributed-systems/distributed-kv-store/complete-design) | write-ahead logging, LSM storage, quorum replication, tombstones and TTL |
| [Design a Distributed Message Queue & Pub/Sub System](https://seeitflow.com/system-design/advanced-distributed-systems/distributed-message-queue/complete-design) | durable work queues, partitioned logs, consumer groups and offsets, idempotent consumers |
| [Design a Distributed Rate Limiter](https://seeitflow.com/system-design/advanced-distributed-systems/distributed-rate-limiter/complete-design) | token buckets, atomic shared counters, fail-open versus fail-closed, multi-region quota leases |
| [Design a Distributed Logging System](https://seeitflow.com/system-design/advanced-distributed-systems/distributed-logging/complete-design) | log agents with bounded spools, durable partitioned buffering, full-text versus label-chunk storage, tenant-scoped queries |
| [Design a Multi-Tenant Feature Flag System](https://seeitflow.com/system-design/intermediate/feature-flag-system/complete-design) | local SDK evaluation, tenant isolation, stable percentage rollouts, control-plane outage safety |

### Search, data and AI systems

| System design | Core engineering challenges |
| --- | --- |
| [Search & Autocomplete](https://seeitflow.com/system-design/foundations/search-autocomplete/complete-design) | inverted indexes, indexing pipelines, prefix-trie autocomplete, sharding and caching |
| [Design a Distributed Web Crawler](https://seeitflow.com/system-design/advanced-distributed-systems/web-crawler/complete-design) | per-origin politeness, durable leased frontier, deduplication, conditional recrawl |
| [Design a Recommendation System](https://seeitflow.com/system-design/intermediate/recommendation-system/complete-design) | candidate generation, multi-stage ranking, feature stores, feedback loops |
| [Design ChatGPT / AI Assistant](https://seeitflow.com/system-design/ai-systems/chatgpt/complete-design) | response streaming, retrieval-augmented context, memory and tools, cost control |
| [Enterprise RAG Knowledge Assistant](https://seeitflow.com/system-design/ai-systems/rag-system/complete-design) | durable ingestion, hybrid retrieval, authorization before generation, citation validation |
| [Design an AI Gateway](https://seeitflow.com/system-design/ai-systems/ai-gateway/complete-design) | model-aware routing, atomic budget admission, streaming failure semantics, control and data planes |

<!-- END GENERATED:design -->

## Architecture and production engineering

<!-- BEGIN GENERATED:production -->
### Resilience patterns

- [Retry & Backoff](https://seeitflow.com/core-concepts/core-patterns/retry-backoff) — How to classify errors worth retrying and apply exponential backoff, jitter and retry budgets without overloading a recovering service.
- [Circuit Breaker](https://seeitflow.com/core-concepts/core-patterns/circuit-breaker) — How closed, open and half-open states stop calls to a failing dependency, and how breakers differ from timeouts and fallbacks.
- [Rate Limiting](https://seeitflow.com/core-concepts/core-patterns/rate-limiting) — A comparison of fixed-window, sliding-window, token-bucket and leaky-bucket limiters, and what changes when limits must hold across several servers.
- [Backpressure](https://seeitflow.com/core-concepts/core-patterns/backpressure) — Why buffering alone is not backpressure, and how systems respond to producer-consumer imbalance by blocking, rejecting, dropping or scaling.
- [Bulkhead](https://seeitflow.com/core-concepts/core-patterns/bulkhead) — How separate resource pools per workload stop one failing dependency from exhausting capacity for everything else.
- [Load Shedding](https://seeitflow.com/core-concepts/core-patterns/load-shedding) — How rejecting low-priority work keeps a system useful under overload, and how this differs from rate limiting and circuit breaking.

### Architecture decisions and trade-offs

- [Architecture Fundamentals](https://seeitflow.com/architecture/modules/architecture-fundamentals) — How requirements, quality attributes, constraints and assumptions combine into the decisions that define an architecture.
- [Architecture Decision Making](https://seeitflow.com/architecture/modules/architecture-decision-making) — How to weigh options, judge how reversible a decision is, and record context and consequences in an architecture decision record.
- [Scalability & Capacity](https://seeitflow.com/architecture/modules/scalability-capacity) — How to find the saturated resource and choose between scaling, caching, replicas, connection pooling and sharding.
- [Reliability & Resilience](https://seeitflow.com/architecture/modules/reliability-resilience) — How reliability, availability and durability differ, and how SLIs, SLOs and resilience patterns fit together.
- [Distributed Architecture](https://seeitflow.com/architecture/modules/distributed-architecture) — How partial failure, replication lag and coordination cost shape distributed designs, including CAP, quorums and consensus.
- [Multi-Region Architecture](https://seeitflow.com/architecture/modules/multi-region-architecture) — How active-active and active-passive designs compare, what RTO and RPO mean, and when multi-region is justified over multi-AZ.
- [Performance Architecture](https://seeitflow.com/architecture/modules/performance-architecture) — How to separate performance from scalability, read tail latency, and locate bottlenecks with tracing, profiling and load tests.
- [Architecture Reviews](https://seeitflow.com/architecture/modules/architecture-reviews) — How design, production-readiness, capacity and security reviews differ, and how to prioritize risks using evidence.

### Failure modes and incident analysis

- [Cache Stampede](https://seeitflow.com/production-engineering/modules/cache-stampede) — Why an expired hot key can flood the database, and how request coalescing, TTL jitter and stale-while-revalidate prevent it.
- [Retry Storm](https://seeitflow.com/production-engineering/modules/retry-storm) — How retries amplify a transient failure into an outage, and how limits, budgets and circuit breakers contain it.
- [Cascading Failure](https://seeitflow.com/production-engineering/modules/cascading-failure) — How one slow dependency exhausts shared threads, connections and queues in the services calling it, and how timeouts and bulkheads limit the spread.
- [Kafka Consumer Lag](https://seeitflow.com/production-engineering/modules/kafka-consumer-lag) — What makes Kafka consumers fall behind, why partition count limits how far a consumer group can scale out, and which remedies address the real bottleneck.
- [DB Connection Pool Exhaustion](https://seeitflow.com/production-engineering/modules/database-connection-pool-exhaustion) — How slow queries, long transactions and leaks exhaust a connection pool, and why a bigger pool can make contention worse.
- [Race Condition](https://seeitflow.com/production-engineering/modules/race-condition) — Why overlapping read-modify-write sequences silently lose updates under load, and how locks, atomic operations or optimistic concurrency prevent it.
- [Incident & Postmortem Analysis](https://seeitflow.com/architecture/modules/incident-postmortem) — How to separate trigger, proximate cause, contributing factors and systemic conditions so postmortem actions address root conditions.

<!-- END GENERATED:production -->

## Using the guide for interviews

A practical loop for any design problem: clarify the requirements, estimate the scale, identify the constraints, outline the architecture, then analyze trade-offs and failure modes. Attempt a design on your own first, then compare your reasoning with the matching case study in the [catalogue](#real-world-system-design-catalogue). No resource here guarantees an interview outcome.

## About, contributing and license

This repository is a public educational resource directory published by SeeItFlow. Learn more about the publisher on the [SeeItFlow About page](https://seeitflow.com/about). Complete lessons, visualizations and case studies are on the website and are not part of this repository.

Found a broken link or a technical error, or want to suggest a resource? Use the [issue templates](https://github.com/seeitflow/system-design/issues/new/choose) or read [CONTRIBUTING.md](CONTRIBUTING.md). A change to this catalogue is not automatically a change to the website.

<!-- LICENSE-PENDING: owner decision required; see the release checklist -->
