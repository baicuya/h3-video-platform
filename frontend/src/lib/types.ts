export type User = {
  id: string;
  username: string;
  display_name: string;
  role: "admin" | "user";
  is_active: boolean;
  must_change_password: boolean;
  remark: string | null;
  last_login_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type Asset = {
  id: string;
  kind: "image" | "video" | "audio";
  original_name: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
};

export type VideoJob = {
  id: string;
  user_id: string;
  parent_job_id: string | null;
  mode: "t2v" | "i2v" | "ref2va";
  status: string;
  prompt: string;
  negative_prompt: string | null;
  duration_seconds: number;
  aspect_ratio: string;
  resolution: string;
  seed: number;
  steps: number;
  input_assets: string[];
  queue_position: number | null;
  progress: number | null;
  stage: string | null;
  output_url: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
};

export type PageResult<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};
