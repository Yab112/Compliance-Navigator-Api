import { enableStaffRealm } from "@cn/core/lib/staff-session";

// The admin app signs in to the staff realm only; this must run before the first session refresh
enableStaffRealm();
