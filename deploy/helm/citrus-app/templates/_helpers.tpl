{{/*
Expand the name of the chart.
Returns the chart name (or override) truncated to 63 chars to comply with K8s DNS naming spec.
*/}}
{{- define "citrus-app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.

Usage note: This helper ensures consistent naming across all K8s resources.
During initial deployment, I encountered issues where manually created Services (via kubectl expose)
conflicted with Helm-managed ones due to naming inconsistencies - these helpers prevent that.
*/}}
{{- define "citrus-app.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "citrus-app.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
These labels are injected into every resource's metadata for:
  1. Helm lifecycle management (upgrades, rollbacks, deletions)
  2. Prometheus service discovery (scrapes based on these labels)
  3. K8s resource organization and filtering

CRITICAL: Initial deployment failed because I forgot to call this helper in all-in.yaml,
causing Prometheus to miss service discovery. Always include this in metadata sections.
*/}}
{{- define "citrus-app.labels" -}}
helm.sh/chart: {{ include "citrus-app.chart" . }}
{{ include "citrus-app.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
Used by Services and Deployments to link pods to their controllers.
WARNING: Never modify these labels after initial deployment - changing them breaks
the selector -> pod mapping, causing traffic to be lost.
*/}}
{{- define "citrus-app.selectorLabels" -}}
app.kubernetes.io/name: {{ include "citrus-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "citrus-app.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "citrus-app.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
