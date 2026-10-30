"""Provider marketplace: Guday Geday agents and agencies that get things done with offices.

Property and car brokers (delala) are out of scope: their work is not about government or
institution requirements.

Providers are individuals or companies. Clients hire them through engagements; only
the client of a completed engagement can review it, and every review feeds the trust
score (services/trust_score.py) stored on the provider for sorting.
"""

# Submodules import each other directly. get_engagement and MAX_REQUESTS_PER_HOUR are read through this
# package (provider_service.get_engagement) so a monkeypatch on the package reaches every caller, as it
# did when this was one module.

from .admin import (  # noqa: F401
    _purge_blockers,
    admin_detail,
    admin_list,
    admin_update,
    expire_licenses,
    purge_samples,
    review_provider,
    sample_status,
    verify_external_license,
)
from .common import (  # noqa: F401
    ENTITY_TYPES,
    PROVIDER_TYPES,
    REGIONS,
    SPECIALTIES,
    SUB_CITIES,
    MarketplaceError,
    get,
    get_for_user,
)
from .engagement_actions import (  # noqa: F401
    client_action,
    provider_action,
)
from .engagements import (  # noqa: F401
    CLIENT_HISTORY,
    JOB_GROUPS,
    MAX_REQUESTS_PER_HOUR,
    _event,
    _tell,
    attention,
    client_scope_counts,
    client_view,
    create_hire,
    follow_up_sql,
    get_engagement,
    job_group_counts,
    list_engagements,
    provider_view,
)
from .profile import (  # noqa: F401
    decide_change,
    join,
    owner_view,
    update_me,
)
from .public import (  # noqa: F401
    list_reviews,
    public_list,
    public_profile,
    recent_jobs,
)
from .readiness import (  # noqa: F401
    BIO_MIN,
    PROFILE_REQUIRED,
    refresh_readiness,
    refresh_readiness_all,
)
from .reviews import (  # noqa: F401
    leave_review,
    list_reviews_admin,
    moderate_review,
    reply_to_review,
)
from .staff_hires import (  # noqa: F401
    STAFF_HIRE_ACTIONS,
    admin_hire_detail,
    admin_update_engagement,
    assign_candidates,
    export_engagements_csv,
    resolve_dispute,
    staff_actions,
)
from .stats import (  # noqa: F401
    marketplace_stats,
)
from .teams import (  # noqa: F401
    invite_member,
    request_to_join,
    respond_membership,
    team,
)
from .trust import (  # noqa: F401
    recompute,
)
