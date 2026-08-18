import type { Pace } from "../types/trip";

export const DESTINATION_OPTIONS = [
  "大理",
  "丽江",
  "三亚",
  "厦门",
  "杭州",
  "重庆",
] as const;

export const ORIGIN_OPTIONS = [
  "北京",
  "上海",
  "广州",
  "深圳",
  "成都",
  "杭州",
] as const;

export const PREFERENCE_OPTIONS = [
  "浪漫",
  "美食",
  "自然",
  "文化",
  "户外",
  "室内",
  "冒险",
] as const;

export const PACE_OPTIONS: Pace[] = ["轻松", "适中", "充实"];
