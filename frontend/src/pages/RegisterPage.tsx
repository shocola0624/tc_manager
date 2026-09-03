import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { authApi } from "../api/endpoints";
import type { CurrentUser } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/useI18n";

export function RegisterPage() {
  const { t } = useI18n();
  const { refetch } = useAuth();
  const [name, setName] = useState("");

  const mutation = useMutation<CurrentUser, ApiError, string>({
    mutationFn: (value) => authApi.register(value),
    onSuccess: () => {
      // /auth/me を再取得して AuthProvider の状態を authenticated に切り替える
      refetch();
    },
  });

  return (
    <main>
      <h1>{t("auth.registerTitle")}</h1>
      <p>{t("auth.registerDescription")}</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate(name);
        }}
      >
        <label>
          {t("auth.registerNameLabel")}
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            minLength={1}
            maxLength={100}
          />
        </label>
        <Button type="submit" variant="primary" disabled={mutation.isPending}>
          {mutation.isPending ? t("auth.registerSubmitting") : t("auth.registerSubmit")}
        </Button>
      </form>
      {mutation.isError && <p role="alert">{t(`errors.${mutation.error.code}`)}</p>}
    </main>
  );
}
