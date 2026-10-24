"use client";

/**
 * Состояние сессии: вошёл ли человек, какая компания выбрана, какая роль у этой компании.
 * Всё, что должно переживать перезагрузку (последняя компания, роли, скрытые карточки), лежит в localStorage.
 * Когда бэкенд начнёт хранить «последнюю компанию» и роль на пару «человек + компания», здесь меняется только
 * загрузка и сохранение.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import * as api from "./api";
import { uiRole } from "./labels";
import type { Company, Me, RoleCode } from "./types";

const KEY = "ab-session";
const HIDDEN_KEY = "ab-hidden";

interface Stored {
  authed: boolean;
  companyId: string | null;
  roles: Record<string, RoleCode>;
}

interface Toast {
  id: number;
  text: string;
  action?: { label: string; run: () => void };
}

export type HiddenMap = Record<string, "hide" | "irrelevant">;

interface SessionValue {
  ready: boolean;
  authed: boolean;
  me: Me | null;
  company: Company | null;
  role: RoleCode;
  /** Пока переключаемся на другую компанию: экраны показывают скелетон */
  switching: boolean;
  signIn: (phone: string, password: string) => Promise<void>;
  signOut: () => void;
  selectCompany: (id: string) => void;
  selectRole: (role: RoleCode) => void;
  hidden: HiddenMap;
  setHidden: (cardId: string, state: "hide" | "irrelevant" | null) => void;
  toasts: Toast[];
  toast: (text: string, action?: Toast["action"]) => void;
  dismissToast: (id: number) => void;
  /** Запрос «открыть переключатель компаний» из других мест (например, «Нет доступа») */
  switcherRequest: number;
  requestSwitcher: () => void;
}

const Ctx = createContext<SessionValue | null>(null);

function readStored(): Stored {
  try {
    return { authed: false, companyId: null, roles: {}, ...JSON.parse(localStorage.getItem(KEY) ?? "{}") };
  } catch {
    return { authed: false, companyId: null, roles: {} };
  }
}

function readHidden(): HiddenMap {
  try {
    return JSON.parse(localStorage.getItem(HIDDEN_KEY) ?? "{}");
  } catch {
    return {};
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [stored, setStored] = useState<Stored>({ authed: false, companyId: null, roles: {} });
  const [me, setMe] = useState<Me | null>(null);
  const [switching, setSwitching] = useState(false);
  const [hidden, setHiddenState] = useState<HiddenMap>({});
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [switcherRequest, setSwitcherRequest] = useState(0);
  const toastId = useRef(0);

  // Восстановление из localStorage после гидратации. Читать хранилище при первом рендере нельзя: на сервере его нет
  useEffect(() => {
    const s = readStored();
    /* eslint-disable react-hooks/set-state-in-effect */
    setStored(s);
    setHiddenState(readHidden());
    if (s.authed) {
      api.getMe().then((m) => {
        setMe(m);
        setReady(true);
      });
    } else {
      setReady(true);
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  const persist = useCallback((next: Stored) => {
    setStored(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* без хранилища всё равно работаем */
    }
  }, []);

  const dismissToast = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const toast = useCallback(
    (text: string, action?: Toast["action"]) => {
      const id = ++toastId.current;
      setToasts((t) => [...t.slice(-2), { id, text, action }]);
      setTimeout(() => dismissToast(id), action ? 6000 : 3500);
    },
    [dismissToast],
  );

  const signIn = useCallback(
    async (phone: string, password: string) => {
      const m = await api.login(phone, password);
      setMe(m);
      // Открывается последняя выбранная компания, если её нет, первая по списку
      const prev = readStored();
      const known = m.companies.some((c) => c.id === prev.companyId);
      persist({
        authed: true,
        companyId: known ? prev.companyId : (m.lastCompanyId ?? m.companies[0]?.id ?? null),
        roles: prev.roles,
      });
    },
    [persist],
  );

  const signOut = useCallback(() => {
    persist({ ...stored, authed: false });
    setMe(null);
  }, [persist, stored]);

  const company = useMemo<Company | null>(() => {
    if (!me) return null;
    return me.companies.find((c) => c.id === stored.companyId) ?? me.companies[0] ?? null;
  }, [me, stored.companyId]);

  const role: RoleCode = company ? (stored.roles[company.id] ?? api.defaultRole(company.id)) : "cfo";

  const selectCompany = useCallback(
    (id: string) => {
      if (!me || id === company?.id) return;
      const c = me.companies.find((x) => x.id === id);
      if (!c) return;
      persist({ ...stored, companyId: id });
      setSwitching(true);
      setTimeout(() => setSwitching(false), 800);
      toast(`Переключились на ${c.name}`);
    },
    [me, company, persist, stored, toast],
  );

  const selectRole = useCallback(
    (r: RoleCode) => {
      if (!company) return;
      const ui = uiRole(r);
      persist({ ...stored, roles: { ...stored.roles, [company.id]: ui } });
    },
    [company, persist, stored],
  );

  const setHidden = useCallback((cardId: string, state: "hide" | "irrelevant" | null) => {
    setHiddenState((prev) => {
      const next = { ...prev };
      if (state) next[cardId] = state;
      else delete next[cardId];
      try {
        localStorage.setItem(HIDDEN_KEY, JSON.stringify(next));
      } catch {
        /* ничего */
      }
      return next;
    });
  }, []);

  const value: SessionValue = {
    ready,
    authed: stored.authed && !!me,
    me,
    company,
    role,
    switching,
    signIn,
    signOut,
    selectCompany,
    selectRole,
    hidden,
    setHidden,
    toasts,
    toast,
    dismissToast,
    switcherRequest,
    requestSwitcher: () => setSwitcherRequest((n) => n + 1),
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession вне SessionProvider");
  return v;
}
