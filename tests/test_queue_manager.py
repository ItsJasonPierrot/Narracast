import queue
import unittest

from narracast.audio_polish import AudioPolishSettings
from narracast import queue_manager
from narracast.queue_manager import Job


class QueueManagerTests(unittest.TestCase):
    def setUp(self):
        with queue_manager._jobs_lock:
            queue_manager._jobs.clear()
        self._drain_work_queue()

    def tearDown(self):
        with queue_manager._jobs_lock:
            queue_manager._jobs.clear()
        self._drain_work_queue()

    def _drain_work_queue(self):
        while True:
            try:
                queue_manager._work_q.get_nowait()
            except queue.Empty:
                return
            else:
                queue_manager._work_q.task_done()

    def test_list_jobs_returns_snapshot(self):
        job = Job(text="hello", status="pending")
        with queue_manager._jobs_lock:
            queue_manager._jobs.append(job)

        listed = queue_manager.list_jobs()
        listed[0].status = "mutated"

        self.assertEqual(queue_manager.get_job(job.id).status, "pending")

    def test_cancel_pending_job(self):
        job = Job(text="hello", status="pending")
        with queue_manager._jobs_lock:
            queue_manager._jobs.append(job)

        result = queue_manager.cancel_job(job.id)

        self.assertEqual(result, "cancelled")
        self.assertTrue(queue_manager.get_job(job.id).cancel_requested)
        self.assertEqual(queue_manager.get_job(job.id).progress, "Cancelling…")

    def test_cancel_generating_job_is_rejected(self):
        job = Job(text="hello", status="generating")
        with queue_manager._jobs_lock:
            queue_manager._jobs.append(job)

        self.assertEqual(queue_manager.cancel_job(job.id), "active")
        self.assertFalse(queue_manager.get_job(job.id).cancel_requested)

    def test_retry_failed_job_queues_copy(self):
        failed = Job(
            text="failed text",
            title="Book",
            part="Part 1",
            voice="voice",
            speed=1.2,
            preset="Fast",
            status="error",
        )
        with queue_manager._jobs_lock:
            queue_manager._jobs.append(failed)

        result, retry = queue_manager.retry_job(failed.id)

        self.assertEqual(result, "queued")
        self.assertIsNotNone(retry)
        self.assertNotEqual(retry.id, failed.id)
        self.assertEqual(retry.text, failed.text)
        self.assertEqual(retry.preset, "Fast")
        self.assertEqual(retry.status, "pending")
        self.assertEqual(len(queue_manager.list_jobs()), 2)

    def test_retry_non_error_job_is_rejected(self):
        pending = Job(text="pending text", status="pending")
        with queue_manager._jobs_lock:
            queue_manager._jobs.append(pending)

        result, retry = queue_manager.retry_job(pending.id)

        self.assertEqual(result, "not_error")
        self.assertEqual(retry.id, pending.id)
        self.assertEqual(len(queue_manager.list_jobs()), 1)

    def test_clear_finished_jobs_keeps_active_jobs(self):
        jobs = [
            Job(status="pending"),
            Job(status="generating"),
            Job(status="done"),
            Job(status="error"),
            Job(status="cancelled"),
        ]
        with queue_manager._jobs_lock:
            queue_manager._jobs.extend(jobs)

        removed = queue_manager.clear_finished_jobs()
        statuses = [job.status for job in queue_manager.list_jobs()]

        self.assertEqual(removed, 3)
        self.assertEqual(statuses, ["pending", "generating"])

    def test_cancel_missing_job_returns_missing(self):
        self.assertEqual(queue_manager.cancel_job("nonexistent"), "missing")

    def test_cancel_done_job_returns_not_pending(self):
        job = Job(status="done")
        with queue_manager._jobs_lock:
            queue_manager._jobs.append(job)
        self.assertEqual(queue_manager.cancel_job(job.id), "not_pending")

    def test_retry_missing_job_returns_missing(self):
        result, job = queue_manager.retry_job("nonexistent")
        self.assertEqual(result, "missing")
        self.assertIsNone(job)

    def test_get_job_missing_returns_none(self):
        self.assertIsNone(queue_manager.get_job("doesnotexist"))

    def test_list_jobs_reverse(self):
        jobs = [Job(status="pending"), Job(status="generating"), Job(status="done")]
        with queue_manager._jobs_lock:
            queue_manager._jobs.extend(jobs)

        ids_forward = [j.id for j in queue_manager.list_jobs(reverse=False)]
        ids_reverse = [j.id for j in queue_manager.list_jobs(reverse=True)]

        self.assertEqual(ids_forward, list(reversed(ids_reverse)))

    def test_retry_preserves_paragraph_pause_ms(self):
        failed = Job(
            text="text",
            title="Book",
            part="1",
            voice="v",
            speed=1.0,
            preset="Balanced",
            paragraph_pause_ms=800,
            status="error",
        )
        with queue_manager._jobs_lock:
            queue_manager._jobs.append(failed)

        result, retry = queue_manager.retry_job(failed.id)

        self.assertEqual(result, "queued")
        self.assertEqual(retry.paragraph_pause_ms, 800)

    def test_retry_preserves_audio_polish_settings(self):
        polish = AudioPolishSettings(
            bitrate="320k",
            normalize=True,
            fade_in_ms=250,
            fade_out_ms=500,
            trim_silence=True,
        )
        failed = Job(
            text="text",
            title="Book",
            part="1",
            voice="v",
            speed=1.0,
            preset="Balanced",
            audio_polish=polish.to_dict(),
            status="error",
        )
        with queue_manager._jobs_lock:
            queue_manager._jobs.append(failed)

        result, retry = queue_manager.retry_job(failed.id)

        self.assertEqual(result, "queued")
        self.assertEqual(retry.audio_polish, polish.to_dict())

    def test_retry_preserves_project_chapter_ids(self):
        failed = Job(
            text="text",
            title="Book",
            part="Chapter 1",
            voice="v",
            status="error",
            project_id="project-1",
            chapter_id="chapter-1",
        )
        with queue_manager._jobs_lock:
            queue_manager._jobs.append(failed)

        result, retry = queue_manager.retry_job(failed.id)

        self.assertEqual(result, "queued")
        self.assertEqual(retry.project_id, "project-1")
        self.assertEqual(retry.chapter_id, "chapter-1")

    def test_add_to_queue_preserves_audio_polish_settings(self):
        original_get_voice_files = queue_manager.get_voice_files
        polish = AudioPolishSettings(
            bitrate="256k",
            normalize=True,
            fade_in_ms=100,
            fade_out_ms=200,
            trim_silence=True,
        )
        queue_manager.get_voice_files = lambda: {"voice": "/tmp/reference.wav"}
        try:
            result = queue_manager.add_to_queue(
                "Some text.",
                "voice",
                1.0,
                "Book",
                "1",
                "Balanced",
                audio_polish=polish,
            )
        finally:
            queue_manager.get_voice_files = original_get_voice_files

        self.assertIn("Queued", result)
        jobs = queue_manager.list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].audio_polish, polish.to_dict())

    def test_add_to_queue_stores_project_chapter_ids(self):
        original_get_voice_files = queue_manager.get_voice_files
        queue_manager.get_voice_files = lambda: {"voice": "/tmp/reference.wav"}
        try:
            result = queue_manager.add_to_queue(
                "Some text.",
                "voice",
                1.0,
                "Book",
                "Chapter 1",
                "Balanced",
                project_id="project-1",
                chapter_id="chapter-1",
            )
        finally:
            queue_manager.get_voice_files = original_get_voice_files

        self.assertIn("Queued", result)
        job = queue_manager.list_jobs()[0]
        self.assertEqual(job.project_id, "project-1")
        self.assertEqual(job.chapter_id, "chapter-1")

    def test_add_to_queue_rejects_empty_text(self):
        result = queue_manager.add_to_queue("   ", "any_voice", 1.0, "", "", "Balanced")
        self.assertIn("paste some text", result)

    def test_add_to_queue_rejects_invalid_voice(self):
        result = queue_manager.add_to_queue("Some text.", "ghost_voice", 1.0, "", "", "Balanced")
        self.assertIn("reference voice", result)


if __name__ == "__main__":
    unittest.main()
