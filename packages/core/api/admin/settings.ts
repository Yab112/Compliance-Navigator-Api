"use client";

import { apiPaths } from "../../lib/constants/api-paths";
import { MTD } from "../../lib/constants/methods";
import type { PlatformSettings, SettingChange, SettingValue } from "../../types/settings";
import { withQuery } from "../catalog/with-query";
import { useAdminMutation, useAdminQuery } from "./use-admin-query";

export const SETTINGS_HISTORY_PAGE_SIZE = 20;

/** Every editable business rule, grouped, with its limits and current value. */
export const usePlatformSettings = () => useAdminQuery<PlatformSettings>(["settings"], apiPaths.admin.settings);

export const useSettingsHistory = (page = 0) =>
  useAdminQuery<{ items: SettingChange[]; total: number }>(
    ["settings", "history", page],
    withQuery(apiPaths.admin.settingsHistory, { limit: SETTINGS_HISTORY_PAGE_SIZE, offset: page * SETTINGS_HISTORY_PAGE_SIZE }),
  );

/** Save several fields at once (all validated first) or put one back to its default. */
export const useSaveSettings = () => {
  const { run, isPending } = useAdminMutation<PlatformSettings, { values: Record<string, SettingValue> }>();
  const save = (values: Record<string, SettingValue>) => run(apiPaths.admin.settings, MTD.PATCH, { values });
  const reset = (key: string) => run(apiPaths.admin.setting(key), MTD.DELETE);
  return { save, reset, isPending };
};
