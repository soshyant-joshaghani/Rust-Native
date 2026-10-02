use std::sync::Mutex;

use async_trait::async_trait;
use sqlx::PgPool;
use uuid::Uuid;

use crate::core::db::db_err;
use crate::core::error::ApiResult;
use crate::modules::apps::sample::schemas::Note;

#[async_trait]
pub trait NoteRepository: Send + Sync {
    /// Newest `updated_at` first.
    async fn list_by_owner(&self, owner_id: Uuid) -> ApiResult<Vec<Note>>;
    async fn get_by_id(&self, id: Uuid) -> ApiResult<Option<Note>>;
    async fn create(&self, note: Note) -> ApiResult<Note>;
    /// Writes title, content and updated_at (matched by id).
    async fn update(&self, note: Note) -> ApiResult<Note>;
    async fn delete(&self, id: Uuid) -> ApiResult<()>;
    async fn delete_by_owner(&self, owner_id: Uuid) -> ApiResult<()>;
}

const NOTE_COLUMNS: &str = "id, title, content, owner_id, created_at, updated_at";

pub struct PgNoteRepository {
    pool: PgPool,
}

impl PgNoteRepository {
    pub fn new(pool: PgPool) -> Self {
        PgNoteRepository { pool }
    }
}

#[async_trait]
impl NoteRepository for PgNoteRepository {
    async fn list_by_owner(&self, owner_id: Uuid) -> ApiResult<Vec<Note>> {
        let sql = format!(
            "SELECT {} FROM note WHERE owner_id = $1 ORDER BY updated_at DESC",
            NOTE_COLUMNS
        );
        sqlx::query_as::<_, Note>(&sql)
            .bind(owner_id)
            .fetch_all(&self.pool)
            .await
            .map_err(db_err)
    }

    async fn get_by_id(&self, id: Uuid) -> ApiResult<Option<Note>> {
        let sql = format!("SELECT {} FROM note WHERE id = $1", NOTE_COLUMNS);
        sqlx::query_as::<_, Note>(&sql)
            .bind(id)
            .fetch_optional(&self.pool)
            .await
            .map_err(db_err)
    }

    async fn create(&self, note: Note) -> ApiResult<Note> {
        let sql = format!(
            "INSERT INTO note ({}) VALUES ($1, $2, $3, $4, $5, $6) RETURNING {}",
            NOTE_COLUMNS, NOTE_COLUMNS
        );
        sqlx::query_as::<_, Note>(&sql)
            .bind(note.id)
            .bind(note.title)
            .bind(note.content)
            .bind(note.owner_id)
            .bind(note.created_at)
            .bind(note.updated_at)
            .fetch_one(&self.pool)
            .await
            .map_err(db_err)
    }

    async fn update(&self, note: Note) -> ApiResult<Note> {
        let sql = format!(
            "UPDATE note SET title = $2, content = $3, updated_at = $4 WHERE id = $1 RETURNING {}",
            NOTE_COLUMNS
        );
        sqlx::query_as::<_, Note>(&sql)
            .bind(note.id)
            .bind(note.title)
            .bind(note.content)
            .bind(note.updated_at)
            .fetch_one(&self.pool)
            .await
            .map_err(db_err)
    }

    async fn delete(&self, id: Uuid) -> ApiResult<()> {
        sqlx::query("DELETE FROM note WHERE id = $1")
            .bind(id)
            .execute(&self.pool)
            .await
            .map_err(db_err)?;
        Ok(())
    }

    async fn delete_by_owner(&self, owner_id: Uuid) -> ApiResult<()> {
        sqlx::query("DELETE FROM note WHERE owner_id = $1")
            .bind(owner_id)
            .execute(&self.pool)
            .await
            .map_err(db_err)?;
        Ok(())
    }
}

/// In-memory repository used by the integration tests.
#[derive(Default)]
pub struct InMemoryNoteRepository {
    notes: Mutex<Vec<Note>>,
}

impl InMemoryNoteRepository {
    pub fn new() -> Self {
        InMemoryNoteRepository::default()
    }

    pub fn len(&self) -> usize {
        self.notes.lock().unwrap().len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

#[async_trait]
impl NoteRepository for InMemoryNoteRepository {
    async fn list_by_owner(&self, owner_id: Uuid) -> ApiResult<Vec<Note>> {
        let guard = self.notes.lock().unwrap();
        let mut rows: Vec<Note> = guard
            .iter()
            .filter(|n| n.owner_id == owner_id)
            .cloned()
            .collect();
        rows.sort_by_key(|n| std::cmp::Reverse(n.updated_at));
        Ok(rows)
    }

    async fn get_by_id(&self, id: Uuid) -> ApiResult<Option<Note>> {
        let guard = self.notes.lock().unwrap();
        Ok(guard.iter().find(|n| n.id == id).cloned())
    }

    async fn create(&self, note: Note) -> ApiResult<Note> {
        let mut guard = self.notes.lock().unwrap();
        guard.push(note.clone());
        Ok(note)
    }

    async fn update(&self, note: Note) -> ApiResult<Note> {
        let mut guard = self.notes.lock().unwrap();
        if let Some(slot) = guard.iter_mut().find(|n| n.id == note.id) {
            *slot = note.clone();
        }
        Ok(note)
    }

    async fn delete(&self, id: Uuid) -> ApiResult<()> {
        let mut guard = self.notes.lock().unwrap();
        guard.retain(|n| n.id != id);
        Ok(())
    }

    async fn delete_by_owner(&self, owner_id: Uuid) -> ApiResult<()> {
        let mut guard = self.notes.lock().unwrap();
        guard.retain(|n| n.owner_id != owner_id);
        Ok(())
    }
}
