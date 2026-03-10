import type { Column } from "elements";
import { h } from "vue";
import type { Payment } from "./types";

export const columns: Column<Payment>[] = [
  {
    id: "email",
    label: "Email",
    isSortable: true,
  },
  {
    id: "amount",
    label: "Amount",
    isSortable: true,
    cell: ({ row }) => {
      const amount = Number.parseFloat(row.getValue("amount"));
      const formatted = new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
      }).format(amount);
      return h("div", { class: "text-right font-medium" }, formatted);
    },
  },
];