//! Notes CRUD with a Redis read cache (soft-degrading).
//!
//! Keys: `sample:notes:v1:list:<owner>` (120 s) and `sample:notes:v1:note:<owner>:<id>` (300 s).

use std::sync::Arc;

use chrono::{DateTime, SubsecRound, Utc};
use uuid::Uuid;

use crate::core::cache::Cache;
use crate::core::error::{check_len, ApiError, ApiResult};
use crate::core::state::AppState;
use crate::modules::apps::sample::repository::NoteRepository;
use crate::modules::apps::sample::schemas::{Note, NoteCreate, NotePublic, NoteUpdate};
use crate::modules::base::users::schemas::User;

pub const CACHE_PREFIX: &str = "sample:notes:v1:";
pub const TTL_LIST: u64 = 120;
pub const TTL_NOTE: u64 = 300;

pub fn list_key(owner: Uuid) -> String {
    format!("{}list:{}", CACHE_PREFIX, owner)
}

pub fn note_key(owner: Uuid, note_id: Uuid) -> String {
    format!("{}note:{}:{}", CACHE_PREFIX, owner, note_id)
}

/// Postgres keeps microseconds; truncate so cached and stored values agree.
fn now() -> DateTime<Utc> {
    Utc::now().trunc_subsecs(6)
}

fn not_allowed() -> ApiError {
    ApiError::forbidden("Not allowed to access this note")
}

fn title_empty() -> ApiError {
    ApiError::validation("Title cannot be empty")
}

#[derive(Clone)]
pub struct NoteService {
    notes: Arc<dyn NoteRepository>,
    cache: Arc<dyn Cache>,
}

impl NoteService {
    pub fn new(state: &AppState) -> Self {
        NoteService {
            notes: state.notes.clone(),
            cache: state.cache.clone(),
        }
    }

    async fn cache_put(&self, key: &str, json: String, ttl: u64) {
        self.cache.set(key, &json, ttl).await;
    }

    async fn invalidate_lists(&self, owner: Uuid) {
        self.cache.delete_prefix(&list_key(owner)).await;
    }

    /// Load from Postgres (never the cache) and check ownership: 404 then 403.
    async fn load_owned(&self, user: &User, note_id: Uuid) -> ApiResult<Note> {
        let note = match self.notes.get_by_id(note_id).await? {
            Some(note) => note,
            None => return Err(ApiError::not_found("Note not found")),
        };
        if note.owner_id != user.id {
            return Err(not_allowed());
        }
        Ok(note)
    }

    pub async fn list(&self, user: &User) -> ApiResult<Vec<NotePublic>> {
        let key = list_key(user.id);
        if let Some(raw) = self.cache.get(&key).await {
            if let Ok(cached) = serde_json::from_str::<Vec<NotePublic>>(&raw) {
                return Ok(cached);
            }
        }
        let rows = self.notes.list_by_owner(user.id).await?;
        let out: Vec<NotePublic> = rows.iter().map(NotePublic::from).collect();
        if let Ok(json) = serde_json::to_string(&out) {
            self.cache_put(&key, json, TTL_LIST).await;
        }
        Ok(out)
    }

    pub async fn create(&self, user: &User, input: NoteCreate) -> ApiResult<NotePublic> {
        check_len("title", &input.title, 1, 255)?;
        check_len("content", &input.content, 0, 10000)?;
        let title = input.title.trim().to_string();
        if title.is_empty() {
            return Err(title_empty());
        }
        let stamp = now();
        let note = Note {
            id: Uuid::new_v4(),
            title,
            content: input.content.trim().to_string(),
            owner_id: user.id,
            created_at: stamp,
            updated_at: stamp,
        };
        let saved = self.notes.create(note).await?;
        let public = NotePublic::from(&saved);
        self.invalidate_lists(user.id).await;
        if let Ok(json) = serde_json::to_string(&public) {
            self.cache_put(&note_key(user.id, saved.id), json, TTL_NOTE).await;
        }
        Ok(public)
    }

    pub async fn get(&self, user: &User, note_id: Uuid) -> ApiResult<NotePublic> {
        let key = note_key(user.id, note_id);
        if let Some(raw) = self.cache.get(&key).await {
            if let Ok(cached) = serde_json::from_str::<NotePublic>(&raw) {
                if cached.owner_id != user.id {
                    return Err(not_allowed());
                }
                return Ok(cached);
            }
        }
        let note = self.load_owned(user, note_id).await?;
        let public = NotePublic::from(&note);
        if let Ok(json) = serde_json::to_string(&public) {
            self.cache_put(&key, json, TTL_NOTE).await;
        }
        Ok(public)
    }

    pub async fn update(
        &self,
        user: &User,
        note_id: Uuid,
        input: NoteUpdate,
    ) -> ApiResult<NotePublic> {
        if let Some(title) = &input.title {
            check_len("title", title, 1, 255)?;
        }
        if let Some(content) = &input.content {
            check_len("content", content, 0, 10000)?;
        }
        let mut note = self.load_owned(user, note_id).await?;
        let mut changed = false;
        if let Some(title) = &input.title {
            let trimmed = title.trim();
            if trimmed.is_empty() {
                return Err(title_empty());
            }
            note.title = trimmed.to_string();
            changed = true;
        }
        if let Some(content) = &input.content {
            note.content = content.trim().to_string();
            changed = true;
        }
        if changed {
            note.updated_at = now();
            note = self.notes.update(note).await?;
        }
        let public = NotePublic::from(&note);
        self.invalidate_lists(user.id).await;
        if let Ok(json) = serde_json::to_string(&public) {
            self.cache_put(&note_key(user.id, note_id), json, TTL_NOTE).await;
        }
        Ok(public)
    }

    pub async fn delete(&self, user: &User, note_id: Uuid) -> ApiResult<()> {
        let note = self.load_owned(user, note_id).await?;
        self.notes.delete(note.id).await?;
        self.cache.delete(&note_key(user.id, note_id)).await;
        self.invalidate_lists(user.id).await;
        Ok(())
    }
}
