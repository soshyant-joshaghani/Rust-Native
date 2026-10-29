mod common;

use axum::http::StatusCode;
use common::TestApp;
use rust_native::core::cache::Cache;
use rust_native::modules::apps::sample::service::{list_key, note_key};
use serde_json::{json, Value};
use uuid::Uuid;

const NOTES: &str = "/api/v1/sample/notes";

fn note_url(id: &str) -> String {
    format!("{}/{}", NOTES, id)
}

async fn create_note(app: &TestApp, token: &str, title: &str, content: &str) -> Value {
    let reply = app
        .post(NOTES, Some(token), json!({"title": title, "content": content}))
        .await;
    assert_eq!(reply.status, StatusCode::CREATED, "{}", reply.text);
    reply.body
}

fn id_of(note: &Value) -> String {
    note["id"].as_str().unwrap().to_string()
}

#[tokio::test]
async fn sample_root_needs_no_auth() {
    let app = TestApp::new();
    let reply = app.get("/api/v1/sample", None).await;
    assert_eq!(reply.status, StatusCode::OK);
    assert_eq!(
        reply.body["message"],
        "Sample module \u{2014} see /sample/notes for the canonical CRUD example"
    );
}

#[tokio::test]
async fn notes_require_authentication() {
    let app = TestApp::new();
    assert_eq!(app.get(NOTES, None).await.status, StatusCode::UNAUTHORIZED);
    let created = app.post(NOTES, None, json!({"title": "x"})).await;
    assert_eq!(created.status, StatusCode::UNAUTHORIZED);
    assert_eq!(created.detail(), "Not authenticated");
    let id = Uuid::new_v4().to_string();
    assert_eq!(app.get(&note_url(&id), None).await.status, StatusCode::UNAUTHORIZED);
    assert_eq!(app.delete(&note_url(&id), None).await.status, StatusCode::UNAUTHORIZED);
    let bad = app.get(NOTES, Some("garbage")).await;
    assert_eq!(bad.status, StatusCode::UNAUTHORIZED);
    assert_eq!(bad.detail(), "Could not validate credentials");
}

#[tokio::test]
async fn create_note_trims_and_returns_201() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let token = app.token_for(&alice);

    let note = create_note(&app, &token, "  Hello  ", "  body text \n").await;
    assert_eq!(note["title"], "Hello");
    assert_eq!(note["content"], "body text");
    assert_eq!(note["owner_id"], alice.id.to_string());
    assert!(Uuid::parse_str(note["id"].as_str().unwrap()).is_ok());
    assert!(note["created_at"].as_str().unwrap().ends_with('Z'));
    assert!(note["updated_at"].as_str().unwrap().ends_with('Z'));

    let default_content = app.post(NOTES, Some(&token), json!({"title": "Only title"})).await;
    assert_eq!(default_content.status, StatusCode::CREATED);
    assert_eq!(default_content.body["content"], "");
}

#[tokio::test]
async fn create_note_validation_errors_are_422_strings() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let token = app.token_for(&alice);

    let blank = app.post(NOTES, Some(&token), json!({"title": "   "})).await;
    assert_eq!(blank.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert_eq!(blank.detail(), "Title cannot be empty");

    let empty = app.post(NOTES, Some(&token), json!({"title": ""})).await;
    assert_eq!(empty.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(empty.body["detail"].is_string());

    let missing = app.post(NOTES, Some(&token), json!({"content": "x"})).await;
    assert_eq!(missing.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(missing.body["detail"].is_string());

    let long_title = "t".repeat(256);
    let too_long = app.post(NOTES, Some(&token), json!({"title": long_title})).await;
    assert_eq!(too_long.status, StatusCode::UNPROCESSABLE_ENTITY);

    let long_content = "c".repeat(10001);
    let content_long = app
        .post(NOTES, Some(&token), json!({"title": "ok", "content": long_content}))
        .await;
    assert_eq!(content_long.status, StatusCode::UNPROCESSABLE_ENTITY);

    let edge = app
        .post(NOTES, Some(&token), json!({"title": "t".repeat(255), "content": "c".repeat(10000)}))
        .await;
    assert_eq!(edge.status, StatusCode::CREATED);

    assert!(app.notes.len() == 1, "rejected notes are not stored");
}

#[tokio::test]
async fn list_returns_only_own_notes_newest_first() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let bob = app.add_regular("bob@example.com").await;
    let alice_token = app.token_for(&alice);
    let bob_token = app.token_for(&bob);

    let first = create_note(&app, &alice_token, "first", "").await;
    tokio::time::sleep(std::time::Duration::from_millis(5)).await;
    let second = create_note(&app, &alice_token, "second", "").await;
    create_note(&app, &bob_token, "bobs", "").await;

    let reply = app.get(NOTES, Some(&alice_token)).await;
    assert_eq!(reply.status, StatusCode::OK);
    let items = reply.body.as_array().unwrap();
    assert_eq!(items.len(), 2);
    assert_eq!(id_of(&items[0]), id_of(&second));
    assert_eq!(id_of(&items[1]), id_of(&first));

    let bobs = app.get(NOTES, Some(&bob_token)).await;
    assert_eq!(bobs.body.as_array().unwrap().len(), 1);
}

#[tokio::test]
async fn owner_isolation_403_and_404() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let bob = app.add_regular("bob@example.com").await;
    let alice_token = app.token_for(&alice);
    let bob_token = app.token_for(&bob);

    let note = create_note(&app, &alice_token, "private", "secret").await;
    let url = note_url(&id_of(&note));

    // Even with a warm cache, another owner never sees the note.
    assert_eq!(app.get(&url, Some(&alice_token)).await.status, StatusCode::OK);

    let read = app.get(&url, Some(&bob_token)).await;
    assert_eq!(read.status, StatusCode::FORBIDDEN);
    assert_eq!(read.detail(), "Not allowed to access this note");

    let update = app.patch(&url, Some(&bob_token), json!({"title": "hacked"})).await;
    assert_eq!(update.status, StatusCode::FORBIDDEN);
    assert_eq!(update.detail(), "Not allowed to access this note");

    let delete = app.delete(&url, Some(&bob_token)).await;
    assert_eq!(delete.status, StatusCode::FORBIDDEN);
    assert_eq!(delete.detail(), "Not allowed to access this note");

    let unchanged = app.get(&url, Some(&alice_token)).await;
    assert_eq!(unchanged.body["title"], "private");

    let ghost = note_url(&Uuid::new_v4().to_string());
    for reply in [
        app.get(&ghost, Some(&bob_token)).await,
        app.patch(&ghost, Some(&bob_token), json!({"title": "x"})).await,
        app.delete(&ghost, Some(&bob_token)).await,
    ] {
        assert_eq!(reply.status, StatusCode::NOT_FOUND);
        assert_eq!(reply.detail(), "Note not found");
    }

    let bad_id = app.get(&note_url("not-a-uuid"), Some(&bob_token)).await;
    assert_eq!(bad_id.status, StatusCode::UNPROCESSABLE_ENTITY);
}

#[tokio::test]
async fn update_note_trims_and_validates() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let token = app.token_for(&alice);
    let note = create_note(&app, &token, "old title", "old content").await;
    let url = note_url(&id_of(&note));

    let updated = app
        .patch(&url, Some(&token), json!({"title": "  New  ", "content": " fresh "}))
        .await;
    assert_eq!(updated.status, StatusCode::OK);
    assert_eq!(updated.body["title"], "New");
    assert_eq!(updated.body["content"], "fresh");
    assert_eq!(updated.body["created_at"], note["created_at"]);

    let only_content = app.patch(&url, Some(&token), json!({"content": "again"})).await;
    assert_eq!(only_content.body["title"], "New");
    assert_eq!(only_content.body["content"], "again");

    let blank = app.patch(&url, Some(&token), json!({"title": "   "})).await;
    assert_eq!(blank.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert_eq!(blank.detail(), "Title cannot be empty");

    let empty = app.patch(&url, Some(&token), json!({"title": ""})).await;
    assert_eq!(empty.status, StatusCode::UNPROCESSABLE_ENTITY);

    let noop = app.patch(&url, Some(&token), json!({})).await;
    assert_eq!(noop.status, StatusCode::OK);
    assert_eq!(noop.body["title"], "New");
}

#[tokio::test]
async fn delete_note_returns_204_then_404() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let token = app.token_for(&alice);
    let note = create_note(&app, &token, "temp", "").await;
    let url = note_url(&id_of(&note));

    let deleted = app.delete(&url, Some(&token)).await;
    assert_eq!(deleted.status, StatusCode::NO_CONTENT);
    assert!(deleted.text.is_empty());

    assert_eq!(app.get(&url, Some(&token)).await.status, StatusCode::NOT_FOUND);
    let listed = app.get(NOTES, Some(&token)).await;
    assert!(listed.body.as_array().unwrap().is_empty());
}

// ---- cache behaviour ------------------------------------------------------

#[tokio::test]
async fn create_sets_note_key_and_clears_list_key() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let token = app.token_for(&alice);

    // Warm the list cache.
    app.get(NOTES, Some(&token)).await;
    assert_eq!(app.cache.ttl_of(&list_key(alice.id)), Some(120));

    let note = create_note(&app, &token, "cached", "").await;
    let id = Uuid::parse_str(&id_of(&note)).unwrap();

    assert_eq!(app.cache.ttl_of(&list_key(alice.id)), None, "list key invalidated");
    assert_eq!(app.cache.ttl_of(&note_key(alice.id, id)), Some(300));
    let stored = app.cache.get(&note_key(alice.id, id)).await.unwrap();
    let cached: Value = serde_json::from_str(&stored).unwrap();
    assert_eq!(cached, note, "cache holds the NotePublic JSON");
    assert!(note_key(alice.id, id).starts_with("sample:notes:v1:note:"));
    assert!(list_key(alice.id).starts_with("sample:notes:v1:list:"));
}

#[tokio::test]
async fn list_reads_through_the_cache() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let token = app.token_for(&alice);
    create_note(&app, &token, "one", "").await;

    let first = app.get(NOTES, Some(&token)).await;
    assert_eq!(first.body.as_array().unwrap().len(), 1);
    assert_eq!(app.cache.ttl_of(&list_key(alice.id)), Some(120));

    // Prove the second read is served from the cache, not from the repository.
    app.cache.put_raw(&list_key(alice.id), "[]");
    let second = app.get(NOTES, Some(&token)).await;
    assert!(second.body.as_array().unwrap().is_empty());
}

#[tokio::test]
async fn get_reads_through_the_cache() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let token = app.token_for(&alice);
    let note = create_note(&app, &token, "real title", "").await;
    let id = Uuid::parse_str(&id_of(&note)).unwrap();

    let mut fake = note.clone();
    fake["title"] = json!("from cache");
    app.cache.put_raw(&note_key(alice.id, id), &fake.to_string());

    let reply = app.get(&note_url(&id.to_string()), Some(&token)).await;
    assert_eq!(reply.body["title"], "from cache");

    // A miss falls back to the repository and fills the key (TTL 300 s).
    app.cache.clear();
    let reply = app.get(&note_url(&id.to_string()), Some(&token)).await;
    assert_eq!(reply.body["title"], "real title");
    assert_eq!(app.cache.ttl_of(&note_key(alice.id, id)), Some(300));
}

#[tokio::test]
async fn update_bypasses_cache_and_overwrites_keys() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let token = app.token_for(&alice);
    let note = create_note(&app, &token, "real title", "").await;
    let id = Uuid::parse_str(&id_of(&note)).unwrap();
    app.get(NOTES, Some(&token)).await;
    assert!(app.cache.ttl_of(&list_key(alice.id)).is_some());

    // Stale cache entry: update must work from the repository.
    let mut stale = note.clone();
    stale["title"] = json!("stale");
    stale["content"] = json!("stale content");
    app.cache.put_raw(&note_key(alice.id, id), &stale.to_string());

    let reply = app
        .patch(&note_url(&id.to_string()), Some(&token), json!({"content": "fresh"}))
        .await;
    assert_eq!(reply.status, StatusCode::OK);
    assert_eq!(reply.body["title"], "real title");
    assert_eq!(reply.body["content"], "fresh");

    assert_eq!(app.cache.ttl_of(&list_key(alice.id)), None);
    let stored = app.cache.get(&note_key(alice.id, id)).await.unwrap();
    let cached: Value = serde_json::from_str(&stored).unwrap();
    assert_eq!(cached["title"], "real title");
    assert_eq!(cached["content"], "fresh");
}

#[tokio::test]
async fn delete_bypasses_cache_and_clears_keys() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let token = app.token_for(&alice);
    let note = create_note(&app, &token, "doomed", "").await;
    let id = Uuid::parse_str(&id_of(&note)).unwrap();
    app.get(NOTES, Some(&token)).await;

    let deleted = app.delete(&note_url(&id.to_string()), Some(&token)).await;
    assert_eq!(deleted.status, StatusCode::NO_CONTENT);
    assert!(app.cache.keys().is_empty(), "keys left: {:?}", app.cache.keys());
}

#[tokio::test]
async fn cache_is_scoped_per_owner() {
    let app = TestApp::new();
    let alice = app.add_regular("alice@example.com").await;
    let bob = app.add_regular("bob@example.com").await;
    let alice_token = app.token_for(&alice);
    let bob_token = app.token_for(&bob);
    create_note(&app, &alice_token, "a", "").await;
    app.get(NOTES, Some(&alice_token)).await;
    app.get(NOTES, Some(&bob_token)).await;

    create_note(&app, &bob_token, "b", "").await;
    // Bob's write must not touch Alice's list key.
    assert_eq!(app.cache.ttl_of(&list_key(alice.id)), Some(120));
    assert_eq!(app.cache.ttl_of(&list_key(bob.id)), None);
}

#[tokio::test]
async fn crud_still_works_when_redis_is_down() {
    let app = TestApp::without_cache();
    let alice = app.add_regular("alice@example.com").await;
    let token = app.token_for(&alice);

    let note = create_note(&app, &token, "no cache", "x").await;
    let url = note_url(&id_of(&note));
    assert_eq!(app.get(&url, Some(&token)).await.status, StatusCode::OK);
    assert_eq!(app.get(NOTES, Some(&token)).await.body.as_array().unwrap().len(), 1);
    let updated = app.patch(&url, Some(&token), json!({"title": "still fine"})).await;
    assert_eq!(updated.body["title"], "still fine");
    assert_eq!(app.delete(&url, Some(&token)).await.status, StatusCode::NO_CONTENT);
    assert!(app.cache.keys().is_empty());
}
