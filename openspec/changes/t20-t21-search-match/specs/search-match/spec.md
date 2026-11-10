# search-match

## ADDED Requirements

### Requirement: Authoritative semantic retrieval
System SHALL isolate embedding models and types and filter every hit against current MySQL identity, source version and permissions.

#### Scenario: Index unavailable
- **WHEN** Milvus fails
- **THEN** search returns explicit 503, never a misleading empty success

### Requirement: Grounded weighted matching
System SHALL bind results to frozen evaluation versions, preserve unknown dimensions and compute weighted scores on the server.

#### Scenario: Evidence missing
- **WHEN** a dimension lacks valid resume evidence
- **THEN** its score is unknown and no automatic invitation is emitted
