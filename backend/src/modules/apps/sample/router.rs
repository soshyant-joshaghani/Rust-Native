use axum::body::Bytes;
use axum::extract::{Path, State};
use axum::http::{HeaderMap, StatusCode};
use axum::routing::get;
use axum::{Json, Router};

use crate::core::error::{parse_json, parse_uuid, ApiResult};
use crate::core::state::AppState;
use crate::modules::apps::sample::schemas::{NoteCreate, NotePublic, NoteUpdate};
use crate::modules::apps::sample::service::NoteService;
use crate::modules::base::auth::current_user;
use crate::modules::base::users::schemas::Message;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/sample", get(sample_root))
        .route("/sample/notes", get(list_notes).post(create_note))
        .route(
            "/sample/notes/{id}",
            get(read_note).patch(update_note).delete(delete_note),
        )
}

async fn sample_root() -> Json<Message> {
    Json(Message {
        message: "Sample module \u{2014} see /sample/notes for the canonical CRUD example"
            .to_string(),
    })
}

async fn list_notes(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> ApiResult<Json<Vec<NotePublic>>> {
    let user = current_user(&state, &headers).await?;
    let notes = NoteService::new(&state).list(&user).await?;
    Ok(Json(notes))
}

async fn create_note(
    State(state): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<(StatusCode, Json<NotePublic>)> {
    let user = current_user(&state, &headers).await?;
    let input: NoteCreate = parse_json(&body)?;
    let note = NoteService::new(&state).create(&user, input).await?;
    Ok((StatusCode::CREATED, Json(note)))
}

async fn read_note(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> ApiResult<Json<NotePublic>> {
    let user = current_user(&state, &headers).await?;
    let id = parse_uuid(&id)?;
    let note = NoteService::new(&state).get(&user, id).await?;
    Ok(Json(note))
}

async fn update_note(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
    body: Bytes,
) -> ApiResult<Json<NotePublic>> {
    let user = current_user(&state, &headers).await?;
    let id = parse_uuid(&id)?;
    let input: NoteUpdate = parse_json(&body)?;
    let note = NoteService::new(&state).update(&user, id, input).await?;
    Ok(Json(note))
}

async fn delete_note(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> ApiResult<StatusCode> {
    let user = current_user(&state, &headers).await?;
    let id = parse_uuid(&id)?;
    NoteService::new(&state).delete(&user, id).await?;
    Ok(StatusCode::NO_CONTENT)
}
