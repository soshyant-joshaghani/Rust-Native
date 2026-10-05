use aide::axum::ApiRouter;
use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::Json;
use schemars::JsonSchema;
use serde::Deserialize;

use crate::core::api::{delete, get, patch, post, Body, Created, CurrentUser};
use crate::core::error::{parse_uuid, ApiResult};
use crate::core::state::AppState;
use crate::modules::apps::sample::schemas::{NoteCreate, NotePublic, NoteUpdate};
use crate::modules::apps::sample::service::NoteService;
use crate::modules::base::users::schemas::Message;

/// `{id}`: a note id (UUID; anything else is a 422).
#[derive(Debug, Deserialize, JsonSchema)]
struct NoteId {
    id: String,
}

pub fn router() -> ApiRouter<AppState> {
    ApiRouter::new()
        .api_route("/sample", get(sample_root))
        .api_route("/sample/notes", get(list_notes).merge(post(create_note)))
        .api_route(
            "/sample/notes/{id}",
            get(read_note)
                .merge(patch(update_note))
                .merge(delete(delete_note)),
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
    CurrentUser(user): CurrentUser,
) -> ApiResult<Json<Vec<NotePublic>>> {
    let notes = NoteService::new(&state).list(&user).await?;
    Ok(Json(notes))
}

async fn create_note(
    State(state): State<AppState>,
    CurrentUser(user): CurrentUser,
    Body(input): Body<NoteCreate>,
) -> ApiResult<Created<NotePublic>> {
    let note = NoteService::new(&state).create(&user, input).await?;
    Ok(Created(note))
}

async fn read_note(
    State(state): State<AppState>,
    CurrentUser(user): CurrentUser,
    Path(NoteId { id }): Path<NoteId>,
) -> ApiResult<Json<NotePublic>> {
    let id = parse_uuid(&id)?;
    let note = NoteService::new(&state).get(&user, id).await?;
    Ok(Json(note))
}

async fn update_note(
    State(state): State<AppState>,
    CurrentUser(user): CurrentUser,
    Path(NoteId { id }): Path<NoteId>,
    Body(input): Body<NoteUpdate>,
) -> ApiResult<Json<NotePublic>> {
    let id = parse_uuid(&id)?;
    let note = NoteService::new(&state).update(&user, id, input).await?;
    Ok(Json(note))
}

async fn delete_note(
    State(state): State<AppState>,
    CurrentUser(user): CurrentUser,
    Path(NoteId { id }): Path<NoteId>,
) -> ApiResult<StatusCode> {
    let id = parse_uuid(&id)?;
    NoteService::new(&state).delete(&user, id).await?;
    Ok(StatusCode::NO_CONTENT)
}
