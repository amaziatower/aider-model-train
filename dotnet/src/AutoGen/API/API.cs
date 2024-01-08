﻿// Copyright (c) Microsoft Corporation. All rights reserved.
// API.cs

using System;
using System.Collections.Generic;
using System.Linq;
using AutoGen.OpenAI;

namespace AutoGen
{
    public static class API
    {
        public static IEnumerable<ILLMConfig> GetOpenAIConfigList(
            string apiKey,
            IEnumerable<string>? modelIDs = null)
        {
            var models = modelIDs ?? new[]
            {
                "gpt-3.5-turbo",
                "gpt-3.5-turbo-16k",
                "gpt-4",
                "gpt-4-32k",
                "gpt-4-0613",
                "gpt-4-32k-0613",
                "gpt-4-1106-preview",
            };

            return models.Select(modelId => new OpenAIConfig(apiKey, modelId));
        }

        public static IEnumerable<ILLMConfig> GetAzureOpenAIConfigList(
            string endpoint,
            string apiKey,
            IEnumerable<string> deploymentNames)
        {
            return deploymentNames.Select(deploymentName => new AzureOpenAIConfig(endpoint, deploymentName, apiKey));
        }

        public static IEnumerable<ILLMConfig> ConfigListFromJson(
            string filePath,
            IEnumerable<string>? filterModels = null)
        {
            throw new NotImplementedException();
        }
    }
}
