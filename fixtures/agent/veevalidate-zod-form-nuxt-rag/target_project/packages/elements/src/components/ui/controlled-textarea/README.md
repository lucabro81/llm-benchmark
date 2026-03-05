# ControlledTextarea

A textarea component integrated with a form.

## Props

| Name          | Type     | Description                             |
| :------------ | :------- | :-------------------------------------- |
| `name`        | `string` | The name of the form field.             |
| `label`       | `string` | The label for the textarea.             |
| `placeholder` | `string` | The placeholder text for the textarea.  |

## Events

| Name         | Payload | Description                             |
| :----------- | :------ | :-------------------------------------- |
| `inputClick` | `()`    | Emitted when the textarea is clicked.   |

## Usage

```html
<ControlledTextarea
  name="myTextarea"
  label="Description"
  placeholder="Enter a detailed description"
  @input-click="resetGeneralError"
/>
```
