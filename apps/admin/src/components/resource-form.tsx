import type { Field } from "@/lib/resources";
import { Button, Label, inputClass } from "./ui";

type Values = Record<string, unknown>;

function initial(field: Field, values?: Values): unknown {
  return values ? values[field.name] : field.defaultValue;
}

function FieldInput({ field, values, editing }: { field: Field; values?: Values; editing: boolean }) {
  const value = initial(field, values);
  const disabled = editing && field.createOnly;
  const common = { name: field.name, required: field.required && !disabled, disabled, className: inputClass };
  const text = value === null || value === undefined ? "" : String(value);

  switch (field.type) {
    case "textarea":
      return <textarea {...common} rows={3} defaultValue={text} />;
    case "select":
      return (
        <select {...common} defaultValue={text || field.options?.[0]}>
          {field.options?.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      );
    case "checkbox":
      return (
        <input
          type="checkbox"
          name={field.name}
          defaultChecked={Boolean(value)}
          disabled={disabled}
          className="size-4 accent-[var(--secondary)]"
        />
      );
    case "checkboxes": {
      const selected = new Set(Array.isArray(value) ? value.map(String) : []);
      return (
        <div className="flex flex-wrap gap-3">
          {field.options?.map((o) => (
            <label key={o} className="inline-flex items-center gap-1.5 text-sm">
              <input type="checkbox" name={field.name} value={o} defaultChecked={selected.has(o)} className="accent-[var(--secondary)]" />
              {o}
            </label>
          ))}
        </div>
      );
    }
    case "list":
      return <input {...common} type="text" defaultValue={Array.isArray(value) ? value.join(", ") : text} />;
    case "color":
      return <input {...common} type="color" defaultValue={text || "#FFFFFF"} className="h-10 w-20 rounded-lg border border-border" />;
    case "date":
      return <input {...common} type="date" defaultValue={text} />;
    case "int":
      return <input {...common} type="number" step={1} min={0} defaultValue={text} />;
    case "money":
      return <input {...common} type="text" inputMode="decimal" placeholder="0,00" defaultValue={text} />;
    case "decimal":
      return <input {...common} type="text" inputMode="decimal" placeholder="0.00" defaultValue={text} />;
    default:
      return <input {...common} type="text" defaultValue={text} />;
  }
}

export function ResourceForm({
  fields,
  action,
  values,
  submitLabel,
}: {
  fields: readonly Field[];
  action: (form: FormData) => Promise<void>;
  values?: Values;
  submitLabel: string;
}) {
  const editing = values !== undefined;
  return (
    <form action={action} className="grid gap-4 sm:grid-cols-2">
      {fields.map((field) => (
        <div key={field.name} className={field.type === "textarea" || field.type === "checkboxes" ? "sm:col-span-2" : undefined}>
          <Label label={field.label + (field.required ? " *" : "")} hint={field.hint}>
            <FieldInput field={field} values={values} editing={editing} />
          </Label>
        </div>
      ))}
      <div className="sm:col-span-2">
        <Button type="submit">{submitLabel}</Button>
      </div>
    </form>
  );
}
