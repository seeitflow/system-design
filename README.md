# System Design — A Visual Learning Guide

> **Don't just learn how systems work. See them work.**

A curated system design learning guide by [SeeItFlow](https://seeitflow.com/): <!-- BEGIN GENERATED:count_total -->105<!-- END GENERATED:count_total --> resources covering real-world system design case studies, distributed systems fundamentals, software architecture and production engineering. Every entry links to the complete lesson on SeeItFlow, where the architecture is built up step by step with interactive visualizations rather than static diagrams.

The lessons are currently free to read on SeeItFlow, with no registration required. They suit students, early-career developers, experienced backend engineers and anyone preparing for a system design interview. This repository is the catalogue and navigation layer; the lessons, visualizations and detailed case studies live on the website.

**Start here: [visual system design on SeeItFlow](https://seeitflow.com/system-design).**

## How to use this guide

- **New to system design?** Follow the [recommended learning path](#recommended-learning-path), then work through the [case studies](#system-design-case-studies) from the Foundations level upward.
- **Preparing for interviews?** Go to [system design interview preparation](#system-design-interview-preparation).
- **Already comfortable with the fundamentals?** Jump to the [<!-- BEGIN GENERATED:count_design -->31<!-- END GENERATED:count_design --> system design case studies](#system-design-case-studies) or the [architecture and production engineering](#architecture-and-production-engineering) topics.
- **Interested in AI systems?** Follow the [AI learning path](#recommended-learning-path).

## Table of contents

- [Recommended learning path](#recommended-learning-path)
- [System design case studies](#system-design-case-studies)
- [Foundations and distributed building blocks](#foundations-and-distributed-building-blocks)
- [Architecture and production engineering](#architecture-and-production-engineering)
- [System design interview preparation](#system-design-interview-preparation)
- [About, contributing and license](#about-and-contributing)

## Recommended learning path

This is one reasonable order, not the only one. Skip phases you already know.

1. **Foundations.** Learn how requests travel across networks and how data is stored, indexed, cached and balanced. Start with [Networking and APIs](#networking-and-apis), then [Data storage and indexing](#data-storage-and-indexing) and [Scalability and caching](#scalability-and-caching).
2. **Distributed systems.** Learn how messaging, replication, consistency and coordination behave when machines and networks fail: [Asynchronous communication](#asynchronous-communication), [Consistency and coordination](#consistency-and-coordination), [Real-time delivery](#real-time-delivery) and [Infrastructure and deployment](#infrastructure-and-deployment).
3. **Apply.** Work through complete designs in the [case studies](#system-design-case-studies), grouped by domain and ordered from Foundations upward within each group, using the level SeeItFlow publishes for each one.
4. **Operate.** Study [resilience patterns](#resilience-patterns), [architecture trade-offs](#architecture-decisions-and-trade-offs) and [failure modes](#failure-modes-and-incident-analysis) that decide whether a design survives production.
5. **AI systems (optional branch).** After the foundations, learn the [AI system building blocks](#ai-system-building-blocks) (LLMs, retrieval-augmented generation, vector databases and model serving), then apply them in the [AI system designs](#ai-systems).

## System design case studies

These are learning designs inspired by familiar products. They are educational examples, not company-authored case studies, and they do not describe any company's proprietary or internal architecture. Each design on SeeItFlow is a five-page journey: the complete design with an embedded visual walkthrough, an architecture deep dive, trade-offs and decisions, failure and scale scenarios, and an interview perspective. The links below go to the complete design, which is the starting point for the rest. The Level column shows the track SeeItFlow publishes the design under.

<!-- BEGIN GENERATED:design -->
### Core services and infrastructure

| System design | Level | Core engineering challenges |
| --- | --- | --- |
| [URL Shortener](https://seeitflow.com/system-design/foundations/url-shortener/complete-design) | Foundations | short-code generation, cache-first reads, redirect semantics, viral traffic spikes |
| [Notification System](https://seeitflow.com/system-design/foundations/notification/complete-design) | Foundations | queue-based decoupling, priority lanes, retry storms, delivery tracking |
| [Distributed Task Scheduler](https://seeitflow.com/system-design/foundations/task-scheduler/complete-design) | Foundations | due-job discovery, leader election, worker leases and heartbeats, retries with backoff |
| [Multi-Tenant Feature Flag System](https://seeitflow.com/system-design/intermediate/feature-flag-system/complete-design) | Intermediate | local SDK evaluation, tenant isolation, stable percentage rollouts, control-plane outage safety |
| [Distributed Cache](https://seeitflow.com/system-design/advanced-distributed-systems/distributed-cache/complete-design) | Advanced distributed systems | stampede protection, hot keys, sharding with consistent hashing or hash slots, replica failover |
| [Distributed Rate Limiter](https://seeitflow.com/system-design/advanced-distributed-systems/distributed-rate-limiter/complete-design) | Advanced distributed systems | token buckets, atomic shared counters, fail-open versus fail-closed behavior, multi-region quota leases |
| [Distributed Message Queue and Pub/Sub](https://seeitflow.com/system-design/advanced-distributed-systems/distributed-message-queue/complete-design) | Advanced distributed systems | durable work queues, partitioned logs, consumer groups and offsets, idempotent consumers |
| [Distributed Key-Value Store](https://seeitflow.com/system-design/advanced-distributed-systems/distributed-kv-store/complete-design) | Advanced distributed systems | write-ahead logging, LSM storage, quorum replication, tombstones and TTL |
| [Distributed Logging System](https://seeitflow.com/system-design/advanced-distributed-systems/distributed-logging/complete-design) | Advanced distributed systems | log agents with bounded spools, durable partitioned buffering, full-text versus label-chunk storage, tenant-scoped queries |

### Real-time communication and collaboration

| System design | Level | Core engineering challenges |
| --- | --- | --- |
| [WhatsApp System Design (Messaging Platform)](https://seeitflow.com/system-design/foundations/whatsapp/complete-design) | Foundations | persistent connections, message ordering, offline delivery, group fan-out |
| [Google Docs System Design (Collaborative Editor)](https://seeitflow.com/system-design/intermediate/collab-editor/complete-design) | Intermediate | merging concurrent edits with operational transform, presence, offline sync, sharded document servers |
| [Real-Time Gaming Leaderboard](https://seeitflow.com/system-design/intermediate/leaderboard/complete-design) | Intermediate | sorted-set ranking, deterministic tie-breaking, idempotent score ingestion, season rollover |

### Booking, payments and marketplaces

| System design | Level | Core engineering challenges |
| --- | --- | --- |
| [Ticket Booking System](https://seeitflow.com/system-design/intermediate/ticketbooking/complete-design) | Intermediate | double-booking races, temporary seat holds, hold expiry, admission control for high-demand events |
| [Hotel Reservation System](https://seeitflow.com/system-design/intermediate/hotel-reservation/complete-design) | Intermediate | room-night inventory, last-room races, atomic multi-night allocation, payment crash recovery |
| [Payment System](https://seeitflow.com/system-design/intermediate/payment/complete-design) | Intermediate | idempotency keys, timeout ambiguity, safe retries, provider reconciliation |
| [E-commerce Platform](https://seeitflow.com/system-design/intermediate/ecommerce/complete-design) | Intermediate | inventory reservation, checkout orchestration, transactional outbox, asynchronous fulfillment |
| [Splitwise System Design (Expense Sharing)](https://seeitflow.com/system-design/intermediate/splitwise/complete-design) | Intermediate | split algorithms, immutable ledger, debt simplification, idempotent writes |
| [Uber System Design (Ride-Hailing)](https://seeitflow.com/system-design/advanced-distributed-systems/uber/complete-design) | Advanced distributed systems | geospatial indexing, rider-driver matching, ETA prediction, surge pricing |
| [Stock Exchange](https://seeitflow.com/system-design/advanced-distributed-systems/stock-exchange/complete-design) | Advanced distributed systems | price-time priority matching, deterministic sequencing, durable journaling, fenced failover |

### Social, media and content delivery

| System design | Level | Core engineering challenges |
| --- | --- | --- |
| [File Storage and Sync](https://seeitflow.com/system-design/foundations/filestorage/complete-design) | Foundations | resumable chunked uploads, separating metadata from file data, multi-device sync, conflict resolution |
| [YouTube System Design (Video Streaming)](https://seeitflow.com/system-design/intermediate/youtube/complete-design) | Intermediate | resumable uploads, asynchronous transcoding, adaptive bitrate streaming, CDN delivery |
| [CDN System Design (Global Content Delivery Network)](https://seeitflow.com/system-design/advanced-distributed-systems/cdn/complete-design) | Advanced distributed systems | edge caching, invalidation, origin shielding, anycast routing |
| [Instagram System Design (Social Media)](https://seeitflow.com/system-design/advanced-distributed-systems/instagram/complete-design) | Advanced distributed systems | media uploads, social graph, fan-out on write, the hot-user problem |
| [Twitter/X System Design (Timeline)](https://seeitflow.com/system-design/advanced-distributed-systems/twitter/complete-design) | Advanced distributed systems | hybrid fan-out for celebrity accounts, feed ranking, timeline caching, hot-partition handling |
| [Netflix System Design](https://seeitflow.com/system-design/advanced-distributed-systems/netflix/complete-design) | Advanced distributed systems | control-plane and data-plane separation, asynchronous transcoding, adaptive bitrate delivery, regional resilience |

### Search, data and recommendation

| System design | Level | Core engineering challenges |
| --- | --- | --- |
| [Search and Autocomplete](https://seeitflow.com/system-design/foundations/search-autocomplete/complete-design) | Foundations | inverted indexes, indexing pipelines, prefix-trie autocomplete, sharding and caching |
| [Recommendation System](https://seeitflow.com/system-design/intermediate/recommendation-system/complete-design) | Intermediate | candidate generation, multi-stage ranking, feature stores, feedback loops |
| [Distributed Web Crawler](https://seeitflow.com/system-design/advanced-distributed-systems/web-crawler/complete-design) | Advanced distributed systems | per-origin politeness, durable leased frontier, deduplication, conditional recrawl |

### AI systems

| System design | Level | Core engineering challenges |
| --- | --- | --- |
| [ChatGPT System Design (AI Assistant)](https://seeitflow.com/system-design/ai-systems/chatgpt/complete-design) | AI systems | response streaming, retrieval-augmented context, memory and tools, cost control |
| [Enterprise RAG Knowledge Assistant](https://seeitflow.com/system-design/ai-systems/rag-system/complete-design) | AI systems | durable ingestion, hybrid retrieval, authorization before generation, citation validation |
| [AI Gateway](https://seeitflow.com/system-design/ai-systems/ai-gateway/complete-design) | AI systems | model-aware routing, atomic budget admission, streaming failure semantics, control and data planes |

<!-- END GENERATED:design -->

## Foundations and distributed building blocks

<!-- BEGIN GENERATED:foundation -->
### Networking and APIs

- [HTTP](https://seeitflow.com/networking/foundations/http/fundamentals) — How HTTP methods, status codes, cookies and caching behave, and what changed between HTTP/1.1, HTTP/2 and HTTP/3.
- [DNS](https://seeitflow.com/networking/foundations/dns/fundamentals) — How a hostname is resolved through recursive lookups, and how record types, TTLs and caching influence failover and traffic distribution.
- [TCP](https://seeitflow.com/networking/foundations/tcp/fundamentals) — How a TCP connection is established, kept reliable under packet loss and congestion, and closed.
- [Load Balancer](https://seeitflow.com/networking/traffic-routing/loadbalancer/fundamentals) — How load balancers choose servers, detect unhealthy ones, drain connections and, in multi-region designs, fail over between regions.
- [API Gateway](https://seeitflow.com/networking/traffic-routing/api-gateway/fundamentals) — What a single logical entry point adds to a service architecture: routing, authentication, rate limiting and aggregation.
- [Reverse Proxy (Nginx)](https://seeitflow.com/networking/traffic-routing/reverse-proxy/fundamentals) — What a reverse proxy such as Nginx does in front of servers: TLS termination, routing, caching and availability.
- [CDN Fundamentals](https://seeitflow.com/networking/advanced-networking/cdn/fundamentals) — How edge caches in a content delivery network (CDN) serve content near users, and how TTLs, invalidation and origin shielding shape hit rates.
- [API Design](https://seeitflow.com/core-concepts/fundamentals/api-design) — How to design consistent API contracts, including resource modeling, error handling, pagination and versioning.
- [REST APIs](https://seeitflow.com/core-concepts/fundamentals/rest) — Which constraints make an API RESTful, how method semantics interact with caching, and how REST differs from RPC.
- [gRPC](https://seeitflow.com/core-concepts/fundamentals/grpc) — How Protobuf contracts, streaming calls and deadlines work in gRPC, and when it is a better fit than REST.
- [Pagination](https://seeitflow.com/core-concepts/fundamentals/pagination) — Why offset pagination degrades on deep pages, how cursor and keyset pagination avoid that cost, and how changing data affects results.
- [Idempotency](https://seeitflow.com/core-concepts/fundamentals/idempotency) — How idempotency keys let clients retry safely, and how to handle concurrent duplicates and a reused key with a different payload.

### Data storage and indexing

- [Database Foundations](https://seeitflow.com/core-concepts/data-database-concepts/db-foundations) — How databases store data, run queries, guarantee durability and handle concurrent access before you study indexing or transactions.
- [Database Data Modeling](https://seeitflow.com/core-concepts/data-database-concepts/db-data-modeling) — How keys, constraints, normalization and query-driven design shape a schema, and techniques for migrating it while the system stays online.
- [Database Indexing](https://seeitflow.com/core-concepts/data-database-concepts/db-indexing) — How indexes speed up queries, how composite indexes are ordered, and why the optimizer sometimes ignores an index.
- [Database Transactions & Concurrency](https://seeitflow.com/core-concepts/data-database-concepts/db-transactions-concurrency) — What ACID guarantees, isolation levels, locking and multi-version concurrency control (MVCC) mean, and when optimistic or pessimistic concurrency fits.
- [Specialized Data Stores](https://seeitflow.com/core-concepts/data-database-concepts/db-specialized-data) — A comparison of relational, document, key-value, search, time-series, graph and vector databases, with guidance on matching each to a workload.
- [PostgreSQL](https://seeitflow.com/databases/technologies/postgres/fundamentals) — How PostgreSQL implements MVCC, indexing, query planning, write-ahead logging and streaming replication.
- [MongoDB](https://seeitflow.com/databases/technologies/mongodb/fundamentals) — How MongoDB handles flexible schemas, aggregation, multi-document transactions, replication and sharding.
- [Cassandra](https://seeitflow.com/databases/technologies/cassandra/fundamentals) — How Cassandra partitions and replicates data across a masterless cluster with tunable consistency, gossip and compaction.
- [Elasticsearch](https://seeitflow.com/databases/technologies/elasticsearch/fundamentals) — How inverted indexes, relevance scoring and sharding enable near-real-time full-text search across a cluster.

### Scalability and caching

- [Database Scaling](https://seeitflow.com/core-concepts/data-database-concepts/db-scaling) — Compare query optimization, caching, read replicas and sharding, and recognize the bottlenecks and failure modes that make each one appropriate.
- [Redis](https://seeitflow.com/backend-systems/technologies/redis/fundamentals) — How Redis serves caching, sessions, streams and pub/sub from memory, and how persistence, replication and cluster sharding work.
- [Consistent Hashing](https://seeitflow.com/core-concepts/distributed-patterns/consistent-hashing) — How consistent hashing limits key movement when nodes join or leave, and which problems it does not solve.

### Asynchronous communication

- [Queues & Workers](https://seeitflow.com/core-concepts/async-systems/queues-workers) — Explore queued execution, acknowledgement and redelivery, crashed-worker recovery, and the limits of delivery and processing guarantees.
- [Pub/Sub](https://seeitflow.com/core-concepts/async-systems/pub-sub) — How publish/subscribe fans events out to independent consumers, and how ordering scope, schema changes and, in some brokers, consumer groups behave.
- [Job Processing](https://seeitflow.com/core-concepts/async-systems/job-processing) — How a background job moves through queued, running, retry and failed states, using leases, heartbeats and idempotency.
- [Outbox Pattern](https://seeitflow.com/core-concepts/async-systems/outbox-pattern) — Why writing to a database and publishing an event separately can lose one of them, how an outbox table closes that gap, and why consumers must still deduplicate.
- [Dead-Letter Queues](https://seeitflow.com/core-concepts/async-systems/dead-letter-queues) — How dead-letter queues set aside unprocessable messages for inspection and replay, and why they do not replace a retry policy.
- [Kafka](https://seeitflow.com/backend-systems/technologies/kafka/fundamentals) — Explore partitioned Kafka logs, replication and retention, then per-partition ordering, consumer group assignment, offset commits and recovery.
- [RabbitMQ](https://seeitflow.com/backend-systems/technologies/rabbitmq/fundamentals) — How RabbitMQ routes messages through exchanges and queues, and how acknowledgements, flow control and durability handle failures.

### Consistency and coordination

- [Distributed Data and the CAP Theorem](https://seeitflow.com/core-concepts/data-database-concepts/db-distributed-data) — Reason about replication, partitioning and quorums, and the availability–consistency trade-off that CAP describes during a network partition.
- [Distributed Locks](https://seeitflow.com/core-concepts/distributed-patterns/distributed-locks) — How leases, TTLs and fencing tokens make distributed locks safer, and when a lock is the wrong tool.
- [Saga Pattern](https://seeitflow.com/core-concepts/distributed-patterns/saga-pattern) — How sagas coordinate a multi-service transaction with compensating actions, and how orchestration, choreography and two-phase commit compare.
- [CQRS](https://seeitflow.com/core-concepts/distributed-patterns/cqrs) — Why separating command and query models (command query responsibility segregation, CQRS) can help, why it does not require event sourcing, and when it is worth the complexity.
- [Event Sourcing](https://seeitflow.com/core-concepts/distributed-patterns/event-sourcing) — How state is derived from an immutable event history, and how snapshots and schema evolution work.
- [etcd](https://seeitflow.com/backend-systems/technologies/etcd/fundamentals) — How etcd uses Raft consensus, watches and leases to provide a strongly consistent store for coordination.

### Real-time delivery

- [Polling](https://seeitflow.com/core-concepts/realtime-systems/polling) — How interval polling trades freshness for simplicity, and how adaptive backoff and conditional requests help it scale.
- [Long Polling](https://seeitflow.com/core-concepts/realtime-systems/long-polling) — How holding a request open delivers updates sooner than polling, and how timeouts and reconnects shape the design.
- [Server-Sent Events](https://seeitflow.com/core-concepts/realtime-systems/sse) — How a server streams one-way updates to browsers over an HTTP response (including HTTPS) with Server-Sent Events, and how reconnection, event IDs, heartbeats and proxies interact.
- [WebSockets](https://seeitflow.com/core-concepts/realtime-systems/websockets) — How the WebSocket handshake, heartbeats, authentication and cross-server fan-out work for full-duplex messaging.
- [Presence](https://seeitflow.com/core-concepts/realtime-systems/presence) — How online status is inferred from heartbeats and TTLs, and why presence is approximate.

### Infrastructure and deployment

- [Docker](https://seeitflow.com/backend-systems/technologies/docker/fundamentals) — Understand image layers, container isolation and networking, and how applications are packaged and deployed consistently.
- [Kubernetes](https://seeitflow.com/backend-systems/technologies/kubernetes/fundamentals) — Explore how pods, deployments, services and the control plane schedule, expose and reconcile workloads across a cluster.

### AI system building blocks

- [LLM Overview](https://seeitflow.com/ai/llms/llm-overview) — How text flows through tokens, transformers and next-token generation in a large language model (LLM), and which components and limits matter in applications.
- [RAG Architecture](https://seeitflow.com/ai/rag/rag-overview) — How a retrieval-augmented generation (RAG) pipeline moves from ingestion and chunking to retrieval, context assembly and citation checks.
- [Vector Databases](https://seeitflow.com/ai/rag/vector-databases) — How vector databases store embeddings and build approximate nearest-neighbor indexes with metadata filters, and when brute force is enough.
- [Model Serving](https://seeitflow.com/ai/ai-infrastructure/model-serving) — How LLM endpoints are deployed, routed, health-checked, autoscaled and monitored, including streaming responses and canary releases.

<!-- END GENERATED:foundation -->

## Architecture and production engineering

<!-- BEGIN GENERATED:production -->
### Resilience patterns

- [Retry & Backoff](https://seeitflow.com/core-concepts/core-patterns/retry-backoff) — How to classify errors worth retrying and apply exponential backoff, jitter and retry budgets without overloading a recovering service.
- [Circuit Breaker](https://seeitflow.com/core-concepts/core-patterns/circuit-breaker) — How closed, open and half-open states stop calls to a failing dependency, and how breakers differ from timeouts and fallbacks.
- [Rate Limiting](https://seeitflow.com/core-concepts/core-patterns/rate-limiting) — A comparison of fixed-window, sliding-window, token-bucket and leaky-bucket limiters, and what changes when limits must hold across several servers.
- [Backpressure](https://seeitflow.com/core-concepts/core-patterns/backpressure) — Learn how downstream capacity signals regulate upstream work, and compare bounded buffering, blocking and overload policies when consumers fall behind.
- [Bulkhead](https://seeitflow.com/core-concepts/core-patterns/bulkhead) — How separate resource pools per workload stop one failing dependency from exhausting capacity for everything else.
- [Load Shedding](https://seeitflow.com/core-concepts/core-patterns/load-shedding) — How rejecting low-priority work keeps a system useful under overload, and how this differs from rate limiting and circuit breaking.

### Architecture decisions and trade-offs

- [Architecture Fundamentals](https://seeitflow.com/architecture/modules/architecture-fundamentals) — How requirements, quality attributes, constraints and assumptions combine into the decisions that define an architecture.
- [Architecture Decision Making](https://seeitflow.com/architecture/modules/architecture-decision-making) — How to weigh options, judge how reversible a decision is, and record context and consequences in an architecture decision record.
- [Scalability & Capacity](https://seeitflow.com/architecture/modules/scalability-capacity) — How to find the saturated resource and choose between scaling, caching, replicas, connection pooling and sharding.
- [Reliability & Resilience](https://seeitflow.com/architecture/modules/reliability-resilience) — How reliability, availability and durability differ, and how service-level indicators and objectives (SLIs and SLOs) fit with resilience patterns.
- [Distributed Architecture](https://seeitflow.com/architecture/modules/distributed-architecture) — How partial failure, replication lag and coordination cost shape distributed designs, including CAP, quorums and consensus.
- [Multi-Region Architecture](https://seeitflow.com/architecture/modules/multi-region-architecture) — How active-active and active-passive designs compare, what RTO and RPO mean, and when multi-region is justified over multi-AZ.
- [Performance Architecture](https://seeitflow.com/architecture/modules/performance-architecture) — How to separate performance from scalability, read tail latency, and locate bottlenecks with tracing, profiling and load tests.
- [Data Architecture](https://seeitflow.com/architecture/modules/data-architecture) — Reason about data ownership, systems of record, data contracts, operational versus analytical data, and schema evolution across services.
- [Platform Architecture](https://seeitflow.com/architecture/modules/platform-architecture) — Understand internal developer platforms: self-service capabilities, golden paths versus escape hatches, and the blast radius of a shared control plane.
- [Architecture Evolution and Migration](https://seeitflow.com/architecture/modules/architecture-evolution) — Compare incremental migration approaches such as the strangler fig, dual writes and shadowing, and plan cutover and rollback for live systems.
- [Cost and Efficiency](https://seeitflow.com/architecture/modules/cost-efficiency) — Evaluate fixed versus variable cost and unit economics to judge efficiency trade-offs rather than optimizing capacity in isolation.
- [Security Architecture](https://seeitflow.com/architecture/modules/security-architecture) — Treat security as an architectural decision: threat models, authentication versus authorization, service and user identity, and secrets management.
- [Architecture Reviews](https://seeitflow.com/architecture/modules/architecture-reviews) — How design, production-readiness, capacity and security reviews differ, and how to prioritize risks using evidence.

### Failure modes and incident analysis

- [Cache Stampede](https://seeitflow.com/production-engineering/modules/cache-stampede) — Understand why simultaneous cache misses overload a backend, and how request coalescing, TTL jitter and stale serving limit the amplification.
- [Retry Storm](https://seeitflow.com/production-engineering/modules/retry-storm) — How retries amplify a transient failure into an outage, and how limits, budgets and circuit breakers contain it.
- [Cascading Failure](https://seeitflow.com/production-engineering/modules/cascading-failure) — How one slow dependency exhausts shared threads, connections and queues in the services calling it, and how timeouts and bulkheads limit the spread.
- [Kafka Consumer Lag](https://seeitflow.com/production-engineering/modules/kafka-consumer-lag) — What makes Kafka consumers fall behind, why partition count limits how far a consumer group can scale out, and which remedies address the real bottleneck.
- [Database Connection Pool Exhaustion](https://seeitflow.com/production-engineering/modules/database-connection-pool-exhaustion) — How slow queries, long transactions and leaks exhaust a connection pool, and why a bigger pool can make contention worse.
- [Race Condition](https://seeitflow.com/production-engineering/modules/race-condition) — See how concurrent read-modify-write operations can lose updates, and compare locking, atomic operations and optimistic concurrency as safeguards.
- [Incident and Postmortem Analysis](https://seeitflow.com/architecture/modules/incident-postmortem) — How to separate trigger, proximate cause, contributing factors and systemic conditions, so postmortem actions address more than one root cause.

<!-- END GENERATED:production -->

## System design interview preparation

A practical loop for any design problem: clarify the requirements, estimate the scale, identify the constraints, outline the architecture, then analyze trade-offs and failure modes. Attempt a design on your own first, then compare your reasoning with the matching [case study](#system-design-case-studies). Each case study on SeeItFlow includes an interview perspective page. No resource here guarantees an interview outcome.

## About and contributing

This repository is a public educational resource directory published by SeeItFlow. Learn more on the [SeeItFlow About page](https://seeitflow.com/about). Complete lessons, visualizations and case studies are on the website and are not part of this repository.

Found a broken link or a technical error, or want to suggest a resource? Use the [issue templates](https://github.com/seeitflow/system-design/issues/new/choose) or read [CONTRIBUTING.md](CONTRIBUTING.md). Product feedback is welcome on the [SeeItFlow contact page](https://seeitflow.com/contact).

## License

Copyright (c) 2026 SeeItFlow. All rights reserved. This repository is public but is not open source: see [LICENSE](LICENSE). The SeeItFlow lessons, visualizations, name and branding are not licensed by this repository. Contributions are accepted under the terms in [CONTRIBUTING.md](CONTRIBUTING.md#contribution-terms).
