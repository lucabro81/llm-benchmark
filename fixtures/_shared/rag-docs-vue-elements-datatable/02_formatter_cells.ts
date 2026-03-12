/**
 * EXAMPLE: Custom cell renderers using Vue h() and Intl formatters.
 *
 * Patterns shown:
 * - Import h from "vue" for render functions
 * - Import Column type from "elements"
 * - row.getValue("fieldName") returns the raw cell value (typed as unknown — cast as needed)
 * - Intl.NumberFormat for currency formatting
 * - Intl.DateTimeFormat for date formatting
 * - h("element", { attrs }, children) creates a VNode
 */

import type { Column } from "elements";
import { h } from "vue";

interface Product {
  id: string;
  name: string;
  price: number;
  releaseDate: string; // ISO date string, e.g. "2024-11-15"
}

export const columns: Column<Product>[] = [
  {
    id: "name",
    label: "Product",
    isSortable: true,
  },

  // Currency formatter — Intl.NumberFormat
  {
    id: "price",
    label: "Price",
    isSortable: true,
    cell: ({ row }) => {
      const amount = Number.parseFloat(row.getValue("price") as string);
      const formatted = new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
      }).format(amount);
      // h("element", { class/style/attrs }, textContent)
      return h("div", { class: "text-right font-medium" }, formatted);
    },
  },

  // Date formatter — Intl.DateTimeFormat
  {
    id: "releaseDate",
    label: "Release Date",
    isSortable: true,
    cell: ({ row }) => {
      const rawDate = row.getValue("releaseDate") as string;
      const formatted = new Intl.DateTimeFormat("en-US", {
        dateStyle: "medium", // e.g. "Nov 15, 2024"
      }).format(new Date(rawDate));
      return h("span", { class: "text-sm text-gray-600" }, formatted);
    },
  },
];
