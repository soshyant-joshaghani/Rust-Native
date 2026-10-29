pub mod sample;

use aide::axum::ApiRouter;

use crate::core::state::AppState;

/// Product modules live here: `apps/<name>/` with router, service, repository and schemas.
/// Declare each one above and merge its router below. Routes are documented from their
/// handlers (see `core::api`).
pub fn router() -> ApiRouter<AppState> {
    ApiRouter::new().merge(sample::router::router())
}
