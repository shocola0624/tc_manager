import { useState, type FormEvent } from "react";
import { useCreateActivity, useUpdateActivity } from "../api/hooks";
import type { Activity } from "../api/types";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/useI18n";
import type { User } from "../api/types";
import { combineDateAndTimeToJstIso, splitJstIso } from "./dateTime";
import styles from "./ActivityForm.module.css";

interface ActivityFormProps {
  mode: "create" | "edit";
  activity?: Activity;
  currentUserId: string;
  activeUsers: User[];
  onDone: () => void;
}

/**
 * 作成・編集共通のフォーム。activity_id・announce_message_id は入力項目に含めない
 * (前者はアプリ採番、後者はフェーズ6のDiscord連携でのみ設定される)。
 */
export function ActivityForm({
  mode,
  activity,
  currentUserId,
  activeUsers,
  onDone,
}: ActivityFormProps) {
  const { t } = useI18n();
  const createActivity = useCreateActivity();
  const updateActivity = useUpdateActivity();

  const initialSplit = activity ? splitJstIso(activity.starts_at) : { date: "", time: "" };

  const [title, setTitle] = useState(activity?.title ?? "");
  const [date, setDate] = useState(initialSplit.date);
  const [time, setTime] = useState(initialSplit.time);
  const [durationMin, setDurationMin] = useState(activity?.duration_min ?? 60);
  const [location, setLocation] = useState(activity?.location ?? "");
  const [ownerId, setOwnerId] = useState(activity?.owner_id ?? currentUserId);
  const [description, setDescription] = useState(activity?.description ?? "");
  const [target, setTarget] = useState(activity?.target ?? "");
  const [tasks, setTasks] = useState(activity?.tasks ?? "");
  const [note, setNote] = useState(activity?.note ?? "");

  const pending = createActivity.isPending || updateActivity.isPending;
  const error = mode === "create" ? createActivity.error : updateActivity.error;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const startsAt = combineDateAndTimeToJstIso(date, time);
    const payload = {
      starts_at: startsAt,
      duration_min: durationMin,
      location,
      title,
      description,
      target,
      owner_id: ownerId,
      tasks,
      note,
    };

    if (mode === "create") {
      createActivity.mutate(payload, { onSuccess: onDone });
    } else if (activity) {
      updateActivity.mutate({ activityId: activity.activity_id, payload }, { onSuccess: onDone });
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className={styles.fields}>
        <label>
          {t("activities.formTitle")}
          <input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={1} />
        </label>
        <label>
          {t("activities.formDate")}
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} required />
        </label>
        <label>
          {t("activities.formStartTime")}
          <input type="time" value={time} onChange={(event) => setTime(event.target.value)} required />
        </label>
        <label>
          {t("activities.formDuration")}
          <input
            type="number"
            min={1}
            value={durationMin}
            onChange={(event) => setDurationMin(Number(event.target.value))}
            required
          />
        </label>
        <label>
          {t("activities.formLocation")}
          <input value={location} onChange={(event) => setLocation(event.target.value)} />
        </label>
        <label>
          {t("activities.formOwner")}
          <select value={ownerId} onChange={(event) => setOwnerId(event.target.value)}>
            {activeUsers.map((activeUser) => (
              <option key={activeUser.discord_user_id} value={activeUser.discord_user_id}>
                {activeUser.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("activities.formDescription")}
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <label>
          {t("activities.formTarget")}
          <textarea value={target} onChange={(event) => setTarget(event.target.value)} />
        </label>
        <label>
          {t("activities.formTasks")}
          <textarea value={tasks} onChange={(event) => setTasks(event.target.value)} />
        </label>
        <label>
          {t("activities.formNote")}
          <textarea value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
      </div>

      <div className={styles.footer}>
        <Button type="button" variant="secondary" onClick={onDone}>
          {t("activities.cancelButton")}
        </Button>
        <Button type="submit" variant="cta" disabled={pending}>
          {t("activities.saveButton")}
        </Button>
      </div>
      {error && (
        <p role="alert" className={styles.error}>
          {t(`errors.${error.code}`)}
        </p>
      )}
    </form>
  );
}
