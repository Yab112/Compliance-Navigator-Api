/** Platform settings: the admin form is built from these field definitions, served by the API. */

export type SettingType = "percent" | "money" | "int" | "bool" | "text";
export type SettingValue = number | boolean | string;

export type SettingField = {
  key: string;
  label: string;
  help: string;
  type: SettingType;
  min: number | null;
  max: number | null;
  unit: string | null;
  pattern: string | null;
  pattern_hint: string | null;
  required: boolean;
  placeholder: string | null;
  /** When a change takes effect, e.g. "New payments" */
  applies: string | null;
  value: SettingValue;
  default: SettingValue;
  is_default: boolean;
  updated_by: string | null;
  updated_at: string | null;
};

export type SettingGroup = { key: string; title: string; am: string; description: string; fields: SettingField[] };

export type PlatformSettings = { groups: SettingGroup[]; changed?: string[] };

export type SettingChange = {
  id: number;
  key: string;
  label: string;
  unit: string | null;
  old_value: SettingValue | null;
  new_value: SettingValue | null;
  changed_by: string | null;
  changed_at: string;
};
