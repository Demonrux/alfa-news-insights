"use client";

import { useEffect, useState } from "react";
import { Button } from "@alfalab/core-components/button";
import { Icon, type IconName } from "@/components/ui/Icon";
import { ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";

interface Props {
  icon: IconName;
  title: string;
  text?: string;
  tone?: "neutral" | "danger";
  children?: React.ReactNode;
  role?: "status" | "alert";
}

/** Единый вид пустых состояний и ошибок: иконка, заголовок, пояснение и действие */
export function StateBlock({ icon, title, text, tone = "neutral", children, role = "status" }: Props) {
  return (
    <div className="plate flex flex-col items-center gap-3 px-6 py-12 text-center" role={role}>
      <span className={`state-ico ${tone === "danger" ? "state-ico--alert" : ""}`} aria-hidden="true">
        <Icon name={icon} size={32} />
      </span>
      <h2 className="m-0 mt-1 text-[20px] leading-[26px] font-bold">{title}</h2>
      {text ? <p className="muted m-0 max-w-[380px] text-[15px] leading-[22px]">{text}</p> : null}
      {children}
    </div>
  );
}

/** Состояние по коду ответа API: 403, 429, 422, 502 и всё остальное */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { requestSwitcher } = useSession();
  const status = error instanceof ApiError ? error.status : 502;

  if (status === 403) {
    return (
      <StateBlock
        icon="lock"
        title="Нет доступа к событиям этой компании"
        text="Доступ выдаёт администратор компании в интернет-банке"
      >
        <Button view="secondary" size={48} onClick={requestSwitcher} aria-haspopup="dialog">
          Выбрать другую компанию
        </Button>
      </StateBlock>
    );
  }
  if (status === 429) {
    return (
      <StateBlock icon="clock" title="Новые разборы сегодня недоступны" text="Показываем готовые">
        {onRetry ? (
          <Button view="secondary" size={48} onClick={onRetry}>
            Обновить
          </Button>
        ) : null}
      </StateBlock>
    );
  }
  if (status === 404) {
    return <StateBlock icon="info" title="Такой карточки нет" text="Возможно, она устарела или была скрыта" />;
  }
  return (
    <StateBlock
      icon="alert"
      tone="danger"
      role="alert"
      title="Не удалось загрузить события"
      text="Проверьте соединение или повторите попытку через минуту"
    >
      {onRetry ? (
        <Button view="primary" size={48} onClick={onRetry}>
          Повторить
        </Button>
      ) : null}
    </StateBlock>
  );
}

/** Шаги, которые проходит агент, пока готовит карточку: показываем вместо пустого спиннера */
export function LoadingSteps() {
  const steps = ["Ищем новости", "Сверяем с аналитикой банка", "Сопоставляем с профилем компании", "Проверяем вывод"];
  // Шаги продвигаются сами, пока компонент на экране. Настоящие шаги придут из потока ответа агента
  const [done, setDone] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setDone((s) => Math.min(s + 1, steps.length - 1)), 350);
    return () => clearInterval(t);
  }, [steps.length]);
  return (
    <div className="plate flex flex-col gap-5" role="status" aria-live="polite">
      <ul className="m-0 flex list-none flex-col gap-3 p-0 text-[15px] leading-[22px]">
        {steps.map((s, i) => (
          <li key={s} className={`flex items-center gap-3 ${i >= done ? "muted" : ""} ${i === done ? "font-bold" : ""}`}>
            {i < done ? (
              <span className="grid size-5 place-items-center rounded-full bg-accent text-white">
                <Icon name="check" size={12} />
              </span>
            ) : i === done ? (
              <span className="size-5 animate-spin rounded-full border-[2.5px] border-[#d2d3d9] border-t-accent" aria-hidden="true" />
            ) : (
              <span className="size-5 rounded-full border-2 border-[#d2d3d9]" />
            )}
            {s}
          </li>
        ))}
      </ul>
      <div className="flex flex-col gap-2.5 border-t border-line-2 pt-5" aria-hidden="true">
        <div className="skeleton h-[26px] w-[160px]" />
        <div className="skeleton h-[22px]" />
        <div className="skeleton h-[22px] w-[70%]" />
      </div>
      <p className="muted m-0 text-[13px]">Подготовка занимает от нескольких секунд до пары минут</p>
    </div>
  );
}
