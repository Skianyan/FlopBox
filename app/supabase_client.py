from supabase import create_client

SUPABASE_URL = "https://dtdbnmuskczfthrhasyc.supabase.co"
SUPABASE_KEY = "sb_publishable_ov5T5Ge0n_rvNtVRess-lQ_LJ_vxMU2"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)