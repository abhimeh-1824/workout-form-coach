/**
 * Isolated Mock API Layer for Local Development & Testing
 *
 * Activated exclusively when VITE_USE_MOCK_API === 'true'.
 * Completely isolated from production API client code.
 */

// Initial mock user session
export const MOCK_USER = {
  id: 'usr_0412_alex',
  name: 'Alex Sterling',
  email: 'alex.sterling@athletelab.dev',
  athleteId: 'Athlete #0412',
  avatarUrl: 'https://lh3.googleusercontent.com/aida/AEtjO1XDwpvxjqOfZeUcBpFztZfBzXdTp1otFsQ1ZazZU9cpjyzlQN_xcf6HwR6UwbfLLG7czr0Rh4hiAUr2alF1NJSQwnqBRBUw1vB5ICYxdCN6TeZBAV0ISsozgJ2m-J8U3x23EUNVUyuB_Fcag4NrJPzF4DrML2RJKOqCGK8g7AJXdu01u-zo0o3Sfpi_TG_tS-eAXHBiLpChuqC8LUywmDaVdPVwaLWyBgE6CwOTZTr5ixYkqJq5-ZWWojp0',
  tier: 'Biometrics Pro Core',
  joinedDate: '2024-11-12',
};

// Initial mock jobs database
export let mockJobsDb = [
  {
    job_id: 'job_883_squat',
    session_num: 883,
    exercise: 'squat',
    exercise_name: 'Squat',
    source_type: 'video_upload',
    video_filename: 'squat_set3.mp4',
    status: 'completed',
    progress: 100,
    created_at: new Date(Date.now() - 3600 * 1000 * 2).toISOString(), // 2 hours ago
    error: null,
    processed_video_url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    report: {
      total_reps: 12,
      clean_reps: 10,
      flagged_reps: 2,
      form_score: 87,
      score_diff: '+4.2 vs baseline average',
      avg_rom: 108,
      target_rom: '110°–115°',
      avg_tempo: 2.4,
      eccentric_tempo: 1.6,
      concentric_tempo: 0.8,
      tempo_status: 'CONTROLLED',
      depth_status: 'PARALLEL',
      kinematic_scores: {
        knee_path_tracking: 82,
        spine_neutrality: 94,
        hip_drive_symmetry: 91,
        bar_path_verticality: 88,
      },
    },
    issues: [
      {
        id: 'issue_valgus',
        severity: 'warning',
        title: 'KNEE CAVE (VALGUS)',
        reps_affected: 'Reps 2 & 7',
        description: 'Right knee shifted 4.2° inward during the lowest reversal phase.',
        ai_cue: 'Keep your knees tracking over your toes and focus on spreading the floor.',
      },
      {
        id: 'issue_depth',
        severity: 'notice',
        title: 'SHALLOW DEPTH (REP 4)',
        reps_affected: 'Rep 4 Only',
        description: 'Hip crease stopped slightly above parallel (101° vs 110° standard).',
        ai_cue: 'Allow hips to sink fully to parallel depth before beginning the drive upwards.',
      },
    ],
  },
  {
    job_id: 'job_884_pushup',
    session_num: 884,
    exercise: 'pushup',
    exercise_name: 'Push-up',
    source_type: 'video_upload',
    video_filename: 'pushup_set2.mp4',
    status: 'processing',
    progress: 68,
    created_at: new Date(Date.now() - 600 * 1000).toISOString(), // 10 mins ago
    error: null,
    current_step: 'Analyzing movement and body posture',
    active_inference: 'Rep 7 of 10 • Checking chest depth and elbow angle',
  },
  {
    job_id: 'job_885_lunge',
    session_num: 885,
    exercise: 'lunge',
    exercise_name: 'Lunge',
    source_type: 'youtube_url',
    youtube_url: 'https://youtube.com/watch?v=mock_lunge_01',
    status: 'queued',
    progress: 0,
    created_at: new Date(Date.now() - 300 * 1000).toISOString(), // 5 mins ago
    error: null,
    queue_position: 2,
    estimated_wait: '30 seconds',
  },
  {
    job_id: 'job_882_lunge',
    session_num: 882,
    exercise: 'lunge',
    exercise_name: 'Lunge',
    source_type: 'video_upload',
    video_filename: 'lunge_set1.mp4',
    status: 'completed',
    progress: 100,
    created_at: new Date(Date.now() - 86400 * 1000).toISOString(), // Yesterday
    error: null,
    processed_video_url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    report: {
      total_reps: 20,
      clean_reps: 18,
      flagged_reps: 2,
      form_score: 88,
      score_diff: '+1.8 vs baseline',
      avg_rom: 92,
      target_rom: '90°–95°',
      avg_tempo: 2.2,
      eccentric_tempo: 1.4,
      concentric_tempo: 0.8,
      tempo_status: 'UNIFORM',
      depth_status: 'OPTIMAL',
      kinematic_scores: {
        knee_path_tracking: 88,
        spine_neutrality: 92,
        hip_drive_symmetry: 89,
        bar_path_verticality: 85,
      },
    },
    issues: [
      {
        id: 'issue_lunge_valgus',
        severity: 'notice',
        title: 'MINOR KNEE INWARD TRACKING',
        reps_affected: 'Left leg reps 4 & 8',
        description: 'Left knee slightly shifted inward during the descent.',
        ai_cue: 'Keep toes pointed forward and track knee directly over your second toe.',
      },
    ],
  },
  {
    job_id: 'job_880_pushup_fail',
    session_num: 880,
    exercise: 'pushup',
    exercise_name: 'Push-up',
    source_type: 'video_upload',
    video_filename: 'pushup_floor.mp4',
    status: 'failed',
    progress: 24,
    created_at: new Date(Date.now() - 86400 * 1000 * 1.5).toISOString(),
    error: {
      code: 'ERR_OBSTRUCTED_VIEW',
      title: 'Body Not Fully Visible',
      message: 'Body was partially obstructed or the lighting was too dim to track your reps.',
      details: 'Please ensure your entire body is in frame with good room lighting.',
    },
  },
  {
    job_id: 'job_881_squat',
    session_num: 881,
    exercise: 'squat',
    exercise_name: 'Squat',
    source_type: 'video_upload',
    video_filename: 'squat_set1.mp4',
    status: 'completed',
    progress: 100,
    created_at: new Date(Date.now() - 86400 * 1000 * 5).toISOString(),
    error: null,
    processed_video_url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    report: {
      total_reps: 15,
      clean_reps: 15,
      flagged_reps: 0,
      form_score: 96,
      score_diff: '+5.4 vs baseline',
      avg_rom: 112,
      target_rom: '110°–115°',
      avg_tempo: 2.1,
      eccentric_tempo: 1.3,
      concentric_tempo: 0.8,
      tempo_status: 'STRICT',
      depth_status: 'FULL ROM',
      kinematic_scores: {
        knee_path_tracking: 98,
        spine_neutrality: 96,
        hip_drive_symmetry: 97,
        bar_path_verticality: 94,
      },
    },
    issues: [],
  },
];

// Mock reps generator for back squat
export const MOCK_SQUAT_REPS = [
  {
    rep_number: 1,
    start_time: 4.2,
    end_time: 6.5,
    rom: 112,
    tempo: 2.1,
    score: 92,
    is_flagged: false,
    status_label: 'CLEAN',
    issues: [],
  },
  {
    rep_number: 2,
    start_time: 9.0,
    end_time: 12.1,
    rom: 108,
    tempo: 2.4,
    score: 84,
    is_flagged: true,
    status_label: 'FLAGGED',
    fault_label: 'Knee Valgus (-4.2°)',
    issues: [
      {
        severity: 'warning',
        title: 'Knee Cave (Valgus)',
        description: 'Right knee shifted 4.2° inward during turnaround.',
      },
    ],
  },
  {
    rep_number: 3,
    start_time: 14.2,
    end_time: 17.0,
    rom: 110,
    tempo: 2.3,
    score: 91,
    is_flagged: false,
    status_label: 'CLEAN',
    issues: [],
  },
  {
    rep_number: 4,
    start_time: 19.1,
    end_time: 22.0,
    rom: 101,
    tempo: 2.2,
    score: 76,
    is_flagged: true,
    status_label: 'FLAGGED',
    fault_label: 'Shallow Depth (101°)',
    issues: [
      {
        severity: 'notice',
        title: 'Shallow Depth',
        description: 'Hip crease remained 2.4 inches above parallel knee line.',
      },
    ],
  },
  {
    rep_number: 5,
    start_time: 24.3,
    end_time: 27.2,
    rom: 111,
    tempo: 2.5,
    score: 89,
    is_flagged: false,
    status_label: 'CLEAN',
    issues: [],
  },
  {
    rep_number: 6,
    start_time: 28.5,
    end_time: 31.4,
    rom: 113,
    tempo: 2.6,
    score: 93,
    is_flagged: false,
    status_label: 'CLEAN',
    issues: [],
  },
  {
    rep_number: 7,
    start_time: 33.1,
    end_time: 35.8,
    rom: 107,
    tempo: 2.4,
    score: 85,
    is_flagged: true,
    status_label: 'FLAGGED',
    fault_label: 'Minor Knee Valgus',
    issues: [
      {
        severity: 'warning',
        title: 'Knee Cave',
        description: 'Bilateral inward knee collapse under fatigue.',
      },
    ],
  },
  {
    rep_number: 8,
    start_time: 37.0,
    end_time: 39.8,
    rom: 110,
    tempo: 2.5,
    score: 90,
    is_flagged: false,
    status_label: 'CLEAN',
    issues: [],
  },
  {
    rep_number: 9,
    start_time: 41.2,
    end_time: 44.0,
    rom: 111,
    tempo: 2.6,
    score: 91,
    is_flagged: false,
    status_label: 'CLEAN',
    issues: [],
  },
  {
    rep_number: 10,
    start_time: 45.4,
    end_time: 48.2,
    rom: 109,
    tempo: 2.7,
    score: 88,
    is_flagged: false,
    status_label: 'CLEAN',
    issues: [],
  },
  {
    rep_number: 11,
    start_time: 49.5,
    end_time: 52.4,
    rom: 110,
    tempo: 2.7,
    score: 89,
    is_flagged: false,
    status_label: 'CLEAN',
    issues: [],
  },
  {
    rep_number: 12,
    start_time: 53.8,
    end_time: 56.9,
    rom: 112,
    tempo: 2.8,
    score: 92,
    is_flagged: false,
    status_label: 'CLEAN',
    issues: [],
  },
];

/**
 * Helpers to simulate asynchronous state evolution during polling
 */
export function advanceMockJobProgress(jobId) {
  const job = mockJobsDb.find((j) => j.job_id === jobId);
  if (!job) return null;

  if (job.status === 'queued') {
    job.status = 'processing';
    job.progress = 15;
    job.current_step = 'Reading video frames';
    return { ...job };
  }

  if (job.status === 'processing') {
    job.progress = Math.min(100, job.progress + 20);
    if (job.progress >= 100) {
      job.status = 'completed';
      job.processed_video_url = 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4';
      job.report = job.report || {
        total_reps: 10,
        clean_reps: 9,
        flagged_reps: 1,
        form_score: 91,
        score_diff: '+3.0 vs baseline',
        avg_rom: 109,
        target_rom: '110° Standard',
        avg_tempo: 2.3,
        eccentric_tempo: 1.5,
        concentric_tempo: 0.8,
        tempo_status: 'CONTROLLED',
        depth_status: 'PARALLEL',
        kinematic_scores: {
          knee_path_tracking: 90,
          spine_neutrality: 93,
          hip_drive_symmetry: 92,
          bar_path_verticality: 89,
        },
      };
      job.issues = job.issues || [];
    } else if (job.progress >= 70) {
      job.current_step = 'Evaluating depth and technique';
    } else if (job.progress >= 40) {
      job.current_step = 'Tracking body movement';
    }
    return { ...job };
  }

  return { ...job };
}

export function insertMockJob(newJob) {
  mockJobsDb.unshift(newJob);
  return newJob;
}
